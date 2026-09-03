"""Shared coercion, validation, lore, sequence, and perception helpers."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import re

from story import attire as attire_model
from world import crowds as crowds_model
from story.character_schema import (
    _UNSPACED_SCRIPT,
    _extra_part_placement,
    character_appearance,
    character_body_interior,
    character_extra_parts,
    character_knowledge_config,
    character_name,
    character_name_from_text,
    cue_boundary_pattern,
    name_boundary_pattern,
    name_boundary_regex,
    normalize_character_data,
    persona_extra_parts,
    persona_name,
)
from core.db import get_setting, q, wget
from core.pipeline_context import note_step_warning
from language_runtime import (
    compositor_text, compositor_value, english_linguistic, linguistic,
)
from llm.llm_quality import complete_validated_json
from mind.memory import chat_lorebook_ids, chat_lorebook_weights
from llm.providers import chat_complete
from llm.prompts import get_prompt
from story.provenance_text import strip_engine_provenance
from story.scene import (get_scene, persona_of, sheet_state, NON_AWAKE_GATED,
                   normalize_player_authority, PLAYER_AUTHORITY_GRANTS)
from llm.schemas import normalize_speech_volume
from world.spatial import (
    _body_interior_holder,
    ambient_scope,
    containment_conceals,
    detail_resolves_between,
    effective_room_size,
    entity_arc,
    has_visual,
    hear_level,
    hiding_holders_of,
    merge_scene_with_diff,
    nearby_rooms,
    normalize_room_id,
    room_of,
    same_subject,
    sense_adjusted,
    sight_level,
    visual_level_between,
)
from mind.theory_of_mind import _TOM_CONFIDENCE_CAPS, cap_mind_model_updates


_REACTIVE_STAGES = {
    "preparation", "approach", "contact", "sustained",
}

def _ling(name):
    return linguistic("agents.common", name)


def _text(key, **values):
    return compositor_text(key, **values)


def _dangling_speech(part, language_id=None):
    """The healer pattern for one wound, built from the ONE speech vocabulary.

    A dangling verb and a dangling colon are the same wound from the same cut,
    so what counts as speech is a single pack value (`_SPEECH_CUE`) and the two
    patterns are shapes around it. They were two independent literals before,
    and they drifted: `en`'s verb healer knew `call` and `shout` and its colon
    healer did not, and neither of `ja`'s carried a single Japanese verb while
    its `_SPEECH_CUE` carried eight. The SHAPE stays per-language because the
    wound is: English strands a verb before a comma, Japanese strands the
    quotative particle before a clause-final verb.
    """
    shape = linguistic("agents.common", "_DANGLING_SPEECH", language_id)[part]
    cue = str(linguistic("agents.common", "_SPEECH_CUE", language_id))
    return re.compile(str(shape["pattern"]).replace("{cue}", cue),
                      int(shape.get("flags") or 0))

# Read-only English compatibility views for diagnostics/tests that import the
# historical constants. Runtime guards resolve through the active pack and
# remain context local; these names are not consulted by a story pipeline.
_DANGLING_SPEECH_VERB_RE = _dangling_speech("verb", "en")
_SPEECH_CUE = english_linguistic("agents.common", "_SPEECH_CUE")

def _stem_token(tok):
    """Crude suffix stem for verb matching ('remembers' -> 'remember')."""
    for suf in ("ing", "es", "ed", "s"):
        if len(tok) > len(suf) + 2 and tok.endswith(suf):
            return tok[:-len(suf)]
    return tok


def _predicate_after_name(text_cf, end):
    """The clause remainder belonging to a subject whose name ends at `end`.

    The autonomy vocabulary is deliberately made of ordinary words ('relax',
    'agree', 'enjoy'), so testing for them ANYWHERE in an attempt made any
    sentence containing one read as puppeting: 'Sarah steps back and I enjoy
    the view' rerouted the player's own step-back into an offer for Sarah, and
    'her grip doesn't yield as I push against Sarah' rerouted a push. Cutting
    at the first coordinator or clause break keeps the test on the predicate
    the character is actually the subject of -- 'steps back', not '...and I
    enjoy the view'."""
    tail = text_cf[end:].lstrip(" '’,")
    # Where one subject's predicate ends. The autonomy test is scoped to the
    # clause that actually belongs to the named character, and this is the
    # cut -- see the docstring above for the two live cases it answers.
    cut = _ling("_CLAUSE_BREAKS").search(tail)
    return tail[:cut.start()] if cut else tail


def _is_autonomous_response(verb, text):
    """True when the described outcome is a volitional or involuntary response
    that belongs to the person having it -- submitting, panicking, giving in.

    `text` must already be scoped to ONE subject's predicate (see
    _predicate_after_name); this scans all of it rather than only the leading
    token, because the construction that matters routinely buries the verb
    ('...pushes Dr. Moon over the edge')."""
    # Outcomes only the person undergoing them may declare: interior volition
    # (agreeing, submitting, giving in) and involuntary body events (fainting,
    # panicking, knees buckling). AGENTS.md's AUTHORITY STOPS AT OTHER MINDS makes
    # these the character's own to enact, so a player-authored element whose
    # SUBJECT is a cast member and whose outcome is one of these is rerouted to
    # that character as an OFFER rather than enacted as objective truth (see
    # director._route_authorial_npc_beat). A player act that merely CAUSES such an
    # outcome ('stabs Sarah') is untouched -- the player is the agent there, and
    # the target's response is resolved through the reaction phase.
    v = str(verb or "").strip().casefold()
    if v in _ling("_AUTONOMY_VERBS") or _stem_token(v) in _ling("_AUTONOMY_VERBS"):
        return True
    low = str(text or "").casefold()
    if any(phrase in low for phrase in _ling("_AUTONOMY_PHRASES")):
        return True
    return any(
        tok in _ling("_AUTONOMY_VERBS") or _stem_token(tok) in _ling("_AUTONOMY_VERBS")
        for tok in re.findall(r"[a-z']+", low)
    )


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
def _in_mental_vocabulary(token, key):
    token = str(token or "").strip().lower()
    words = _ling(key)
    return bool(token) and (token in words or _stem_token(token) in words)


def _is_mental_action(verb, attempt):
    """True when an action element is purely interior (no outward surface).

    Answering wrongly here is not recoverable: a blanked `observable` is
    skipped by every deterministic delivery site, so the act reaches no view,
    no percept and no memory, and the only trace is an empty string in a
    stored variant. Two rules keep the guess from overruling an answer.

    A DECLARED VERB DECIDES. The leading-token scan below exists, in this
    docstring's own words, "for a weak model that left verb unset" -- so it
    only runs when the verb is unset. It used to run regardless, and blanked
    `verb: "search"` / `attempt: "feel along the desk surface in total
    darkness, searching by touch for anything resembling a radio unit"`
    because the attempt happened to open with `feel` (live corpus, measured).

    A VERB THAT NAMES BOTH NEEDS AN INWARD OBJECT. `feel`, `focus`, `reflect`,
    `resolve` and `sense` lead ordinary conduct as readily as they lead a
    thought, and the leading token alone cannot tell which. What the act
    REACHES FOR can: turned on the actor's own body or on a state they are in,
    it is interior; directed at anything else, it is not. Held in the pack as
    `_AMBIGUOUS_MENTAL_VERBS` so a language can name its own such verbs.

    Conservative in the other direction too: only the LEAD is classified, so a
    physical act that merely mentions thought later ('carve while recalling
    the shape') is NOT suppressed.
    """
    verb = str(verb or "").strip().lower()
    if verb:
        if _in_mental_vocabulary(verb, "_MENTAL_VERBS"):
            return True
        if not _in_mental_vocabulary(verb, "_AMBIGUOUS_MENTAL_VERBS"):
            return False
        return _reaches_inward(attempt)
    head = re.split(r"[^\w]+", str(attempt or "").strip().lower(), maxsplit=1)
    lead = head[0] if head else ""
    if _in_mental_vocabulary(lead, "_MENTAL_VERBS"):
        return True
    if _in_mental_vocabulary(lead, "_AMBIGUOUS_MENTAL_VERBS"):
        return _reaches_inward(attempt)
    return False


def _reaches_inward(attempt):
    """Whether an act is turned on the actor rather than on the world.

    The markers are the two the pack already keeps for exactly this
    distinction: the actor's own body, and a state a person is in.
    """
    low = str(attempt or "").lower()
    tokens = set(re.findall(r"[\w']+", low))
    if tokens.intersection(_ling("_OWN_BODY_NOUNS")):
        return True
    return any(state in low for state in _ling("_INTERIOR_STATES"))


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


_COMMUNICATIVE_TYPES = frozenset({
    "communication", "communicative_act", "speech_act", "indirect_speech",
})


def communication_surface(elem):
    """Observable indirect-speech predicate for a typed communicative act.

    The returned text is deliberately not a quotation.  ``content`` is the
    proposition the author supplied (ask what happened, explain the route),
    not words the engine is licensed to put in the speaker's mouth.
    """
    if not isinstance(elem, dict):
        return ""
    act = " ".join(str(elem.get("act") or "say").split()).casefold()
    content = " ".join(str(
        elem.get("content") or elem.get("topic") or "").split())
    if not content:
        return ""
    verbs = {
        "ask": "asks", "question": "asks", "explain": "explains",
        "report": "reports", "tell": "tells", "warn": "warns",
        "request": "requests", "offer": "offers", "instruct": "instructs",
        "reassure": "reassures", "promise": "promises", "admit": "admits",
        "answer": "answers", "clarify": "clarifies", "inform": "informs",
        "say": "says",
    }
    verb = verbs.get(act, (act + "s") if act else "says")
    return f"{verb} {content}".strip()


def resolve_action_referents(surface, elem, labels=None):
    """Resolve exact annotated pronoun spans without guessing an antecedent.

    ``labels`` maps canonical entity strings to the observer-safe label the
    caller already earned (a name, ``you``, or an anonymous epithet).  Missing
    mappings fall back to the canonical entity, which is appropriate only for
    objective/narrator surfaces; perception callers pass their display map.
    """
    text = str(surface or "")
    refs = elem.get("referents") if isinstance(elem, dict) else None
    if not text or not isinstance(refs, list):
        return text
    label_map = {
        str(key or "").strip().casefold(): str(value or "").strip()
        for key, value in (labels or {}).items() if str(key or "").strip()
    }
    # Replace later occurrences first so earlier span offsets stay valid.
    replacements = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        needle = str(ref.get("text") or "").strip()
        entity = str(ref.get("entity") or "").strip()
        if not needle or not entity:
            continue
        try:
            occurrence = max(1, int(ref.get("occurrence") or 1))
        except (TypeError, ValueError):
            occurrence = 1
        matches = list(re.finditer(
            rf"(?<!\w){re.escape(needle)}(?!\w)", text, flags=re.I))
        if occurrence > len(matches):
            continue
        match = matches[occurrence - 1]
        label = label_map.get(entity.casefold(), entity)
        role = str(ref.get("role") or "").casefold()
        if "possessive" in role and label.casefold() in ("you", "your"):
            label = "your"
        elif "possessive" in role and label.casefold() not in ("its",):
            label = label + ("'" if label.endswith("s") else "'s")
        replacements.append((match.start(), match.end(), label))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def sequence_onset_elements(sequence):
    """Only phases that exist before anyone has had a chance to react."""
    out = []
    for raw in sequence or []:
        if not isinstance(raw, dict):
            continue
        phase = str(raw.get("phase") or "atomic").casefold()
        if raw.get("depends_on") or phase in ("continuation", "completion"):
            continue
        out.append(raw)
    return out


def _claim_realized(elem, resolved):
    """Whether resolution explicitly realized every claim for one action."""
    if str(elem.get("commitment") or "") != "contestable":
        return True
    resolved = resolved if isinstance(resolved, dict) else {}
    rows = list(resolved.get("claim_dispositions") or [])
    sd = resolved.get("state_diff")
    if isinstance(sd, dict):
        rows.extend(sd.get("claim_dispositions") or [])
    event_id = str(elem.get("event_id") or "").strip()
    match = re.search(r":player:(\d+):action$", event_id)
    sequence_idx = match.group(1) if match else None
    related = []
    realized_ids = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        claim_id = str(row.get("claim_id") or "").strip()
        status = str(row.get("status") or "").casefold()
        if status == "realized":
            realized_ids.update(
                str(value).strip()
                for value in (row.get("realized_event_ids") or [])
                if str(value).strip())
        if claim_id == event_id or (sequence_idx is not None and
                claim_id.startswith(f"claim:{sequence_idx}:")):
            related.append(status)
    return (bool(related) and all(status == "realized" for status in related)) \
        or (not related and bool(event_id and event_id in realized_ids))


def _scene_has_subject(scene, subject):
    wanted = str(subject or "").strip().casefold()
    if not wanted or wanted in {
            "self", "player", "the player", "you", "me", "him", "her",
            "them", "it"}:
        return True
    candidates = set()
    for key in (scene.get("positions") or {}):
        candidates.add(str(key).strip().casefold())
    for key, entity in (scene.get("entities") or {}).items():
        candidates.add(str(key).strip().casefold())
        if isinstance(entity, dict):
            candidates.add(str(entity.get("name") or "").strip().casefold())
            candidates.update(str(alias).strip().casefold()
                              for alias in entity.get("aliases") or [])
    return wanted in candidates


def _scene_has_contact(scene, selector):
    if not isinstance(selector, dict):
        return False
    actor = str(selector.get("actor") or "").strip().casefold()
    target = str(selector.get("target") or "").strip().casefold()
    actor_part = str(selector.get("actor_part") or "").strip().casefold()
    target_part = str(selector.get("target_part") or "").strip().casefold()
    for contact in scene.get("contacts") or []:
        if not isinstance(contact, dict):
            continue
        ca = str(contact.get("actor") or "").strip().casefold()
        ct = str(contact.get("target") or "").strip().casefold()
        cap = str(contact.get("actor_part") or "").strip().casefold()
        ctp = str(contact.get("target_part") or "").strip().casefold()
        direct = ca == actor and ct == target \
            and (not actor_part or cap == actor_part) \
            and (not target_part or ctp == target_part)
        mirror = ca == target and ct == actor \
            and (not actor_part or ctp == actor_part) \
            and (not target_part or cap == target_part)
        if direct or mirror:
            return True
    return False


def settle_sequence_dispositions(sequence, resolved, scene):
    """Compose model adjudication with explicit causal prerequisites.

    The model decides contested outcomes.  The engine decides the structural
    consequence: a dependent phase cannot execute when its prerequisite was
    merely attempted, when a named participant does not exist, or when a
    required standing contact is absent.
    """
    verdicts = []
    by_key = {}
    for index, elem in enumerate(sequence or []):
        if not isinstance(elem, dict):
            continue
        event_id = str(elem.get("event_id") or f"sequence:{index}")
        phase_id = str(elem.get("phase_id") or event_id)
        dependencies = [str(value) for value in elem.get("depends_on") or []
                        if str(value).strip()]
        reason = ""
        for dependency in dependencies:
            parent = by_key.get(dependency)
            if parent is None:
                reason = f"missing prerequisite {dependency}"
                break
            if parent.get("status") not in ("executed", "realized"):
                reason = f"prerequisite {dependency} did not complete"
                break
        if not reason:
            missing = [person for person in elem.get("participants") or []
                       if not _scene_has_subject(scene, person)]
            if missing:
                reason = "missing participant(s): " + ", ".join(missing)
        if not reason:
            missing_contact = next((
                selector for selector in elem.get("requires_contacts") or []
                if not _scene_has_contact(scene, selector)), None)
            if missing_contact is not None:
                reason = "required contact is not standing"
        if reason:
            status = "blocked"
        elif elem.get("type") == "action" \
                and str(elem.get("commitment") or "") == "contestable":
            status = "realized" if _claim_realized(elem, resolved) else "attempted"
        else:
            status = "executed"
        verdict = {
            "event_id": event_id, "phase_id": phase_id,
            "status": status, "reason": reason,
        }
        verdicts.append(verdict)
        by_key[event_id] = verdict
        by_key[phase_id] = verdict
    return verdicts


def sequence_event_allowed(event, resolved):
    """Whether a declared event survived the engine-authored causal floor."""
    event_id = str((event or {}).get("event_id") or "")
    if not event_id:
        return True
    for row in (resolved or {}).get("sequence_dispositions") or []:
        if isinstance(row, dict) and str(row.get("event_id") or "") == event_id:
            return str(row.get("status") or "") != "blocked"
    return True


def prune_blocked_phase_changes(diff, dispositions):
    """Drop state-diff records explicitly sourced from a blocked phase.

    Specialists map each derived channel path or list index to its event id in
    ``phase_sources``.  Untagged legacy output is left alone; this floor never
    guesses which change a prose sentence meant.  Inline ``source_event_id``
    is accepted only as a compatibility input and stripped before persistence.
    """
    if not isinstance(diff, dict):
        return []
    blocked = {
        str(row.get("event_id") or "") for row in dispositions or []
        if isinstance(row, dict) and row.get("status") == "blocked"
    }
    dropped = []
    phase_sources = diff.pop("phase_sources", {})
    numeric_list_drops = {}
    if isinstance(phase_sources, dict):
        for path, source in phase_sources.items():
            source = str(source or "")
            if source not in blocked:
                continue
            channel, dot, key = str(path or "").partition(".")
            value = diff.get(channel)
            if dot and isinstance(value, dict) and key in value:
                value.pop(key, None)
                dropped.append((path, source))
            elif dot and isinstance(value, list):
                if key.isdigit() and int(key) < len(value):
                    numeric_list_drops.setdefault(channel, set()).add(int(key))
                    dropped.append((path, source))
                else:
                    before = len(value)
                    diff[channel] = [item for item in value
                                     if str(item) != key]
                    if len(diff[channel]) != before:
                        dropped.append((path, source))
    for channel, indices in numeric_list_drops.items():
        value = diff.get(channel)
        if isinstance(value, list):
            diff[channel] = [item for index, item in enumerate(value)
                             if index not in indices]
    for channel, value in list(diff.items()):
        if isinstance(value, list):
            kept = []
            for record in value:
                source = (str(record.get("source_event_id") or "")
                          if isinstance(record, dict) else "")
                if source in blocked:
                    dropped.append((channel, source))
                else:
                    if isinstance(record, dict) and "source_event_id" in record:
                        record = dict(record)
                        record.pop("source_event_id", None)
                    kept.append(record)
            diff[channel] = kept
        elif isinstance(value, dict):
            kept = {}
            for key, record in value.items():
                source = (str(record.get("source_event_id") or "")
                          if isinstance(record, dict) else "")
                if source in blocked:
                    dropped.append((f"{channel}.{key}", source))
                else:
                    if isinstance(record, dict) and "source_event_id" in record:
                        record = dict(record)
                        record.pop("source_event_id", None)
                    kept[key] = record
            diff[channel] = kept
    return dropped


def observable_action_onset_text(elem):
    """The part of an action surface available *before* it is adjudicated.

    ``observable_action_text`` is the complete outward surface the interpret
    model extracted from the player's sentence.  That is safe for an asserted
    act, but not automatically safe for a contestable multi-stage act: live
    scenario play handed a dance partner "signals a dip, takes her weight,
    returns her upright, opens both hands, and steps back" in perception pass
    one.  Her reaction therefore arrived after every outcome she existed to
    help resolve.

    Interpret already marks these acts contestable.  For that one class, pass
    one exposes only the first visible phase, stopping at explicit sequencing
    punctuation/words.  The full declaration still reaches resolution
    unchanged.  This is deliberately grammar-level rather than a combat verb
    list: a dip, an examination, a spell, and a grapple receive the same
    causality boundary.
    """
    surface = observable_action_text(elem).strip()
    if not surface or str(elem.get("commitment") or "") != "contestable":
        return surface
    # Observable surfaces are verb-first predicate phrases.  A comma followed
    # by a new verb phrase, a semicolon, or an explicit then/afterward marks a
    # later phase.  Keep coordinating words inside the first phase ("raises
    # both hands and braces") when no stronger sequence boundary appears.
    pieces = re.split(
        r"\s*;\s*|\s*,\s*(?:and\s+)?(?:then\s+)?|\s+\b(?:then|afterward|subsequently)\b\s+",
        surface,
        maxsplit=1,
        flags=re.I,
    )
    onset = pieces[0].strip()
    if not onset:
        return ""

    # A contestable observable describes the motion that is beginning, not an
    # outcome the first perception pass may award. Model-written predicate
    # phrases nevertheless commonly arrive as completed-looking presents --
    # ``creates space`` / ``takes her wrist``. That taught the reacting mind
    # that the very effect it was being asked to contest had already happened,
    # and the same wording could later make narration contradict a rejected
    # disposition (live close-contact audit: the committed pose said the
    # retreat was prevented while the page said ``I create space``).
    #
    # Keep the outward surface rather than `attempt` (which may contain
    # private purpose), but put its first English predicate under explicit
    # attempt modality. Non-Latin/scripted surfaces fall through unchanged;
    # their morphology belongs to the language adapter, not an English
    # conjugation guess here.
    match = re.match(r"([A-Za-z]+)(\b.*)", onset)
    if not match:
        return onset
    verb, tail = match.groups()
    low = verb.casefold()
    if low in ("tries", "attempts", "begins", "starts"):
        return onset
    irregular = {"is": "be", "has": "have", "does": "do", "goes": "go"}
    if low in irregular:
        base = irregular[low]
    elif low.endswith("ies") and len(low) > 3:
        base = low[:-3] + "y"
    elif (low.endswith(("ches", "shes", "xes", "zzes", "oes", "sses"))
          and len(low) > 4):
        base = low[:-2]
    elif low.endswith("s") and not low.endswith("ss") and len(low) > 2:
        base = low[:-1]
    else:
        base = low
    return "attempts to " + base + tail


def adjudicated_player_action_text(elem, resolved=None):
    """Return only the outward portion resolution made true.

    Asserted acts retain their complete observable surface. A contestable act
    does so only when a claim disposition names its event id in
    ``realized_event_ids``; otherwise only the onset is safe. Missing or
    malformed disposition data therefore loses detail instead of inventing a
    successful conditional branch.
    """
    surface = observable_action_text(elem).strip()
    if not surface or str(elem.get("commitment") or "") != "contestable":
        return surface
    resolved = resolved if isinstance(resolved, dict) else {}
    if not sequence_event_allowed(elem, resolved):
        return ""
    sd = resolved.get("state_diff")
    rows = list(resolved.get("claim_dispositions") or [])
    if isinstance(sd, dict):
        rows.extend(sd.get("claim_dispositions") or [])
    event_id = str(elem.get("event_id") or "").strip()
    match = re.search(r":player:(\d+):action$", event_id)
    sequence_idx = match.group(1) if match else None
    related = []
    related_claim_ids = []
    realized_ids = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        claim_id = str(row.get("claim_id") or "").strip()
        status = str(row.get("status") or "").casefold()
        ids = {str(value).strip()
               for value in (row.get("realized_event_ids") or [])
               if str(value).strip()}
        realized_ids.update(ids if status == "realized" else ())
        # Intent claims use claim:<sequence-index>:intent:<effect-index>.
        # Several can belong to one multi-phase action, and one realized
        # effect must not promote its deferred siblings to completed fact.
        if claim_id == event_id or (sequence_idx is not None and
                claim_id.startswith("claim:%s:" % sequence_idx)):
            related.append(status)
            related_claim_ids.append(claim_id)
    fully_realized = bool(related) and all(
        status == "realized" for status in related)
    if not related:
        fully_realized = bool(event_id and event_id in realized_ids)
    if fully_realized:
        return surface
    # An intent-only alternative that was wholly deferred/rejected never
    # began. A direct event disposition of "deferred" is different: the
    # attempted onset may have happened before its effect was prevented.
    intent_only = bool(related_claim_ids) and all(
        claim_id.startswith("claim:") for claim_id in related_claim_ids)
    if intent_only and not any(
            status in ("realized", "begun", "contested")
            for status in related):
        return ""
    return observable_action_onset_text(elem)


#: Characters of one speech line worth searching for provenance. A merged
#: player line is a sentence or three; past this it is not a speech line and
#: the coverage search is not owed to it.
_SPEECH_ANCHOR_MAX_CHARS = 4000


def _speech_anchor_atoms(value):
    """The comparable characters of a text: case, spacing, punctuation gone.

    The unit is the alphanumeric CHARACTER and not the word, because the
    engine runs stories in scripts that do not space their words -- a
    word-split provenance test answers nothing in Japanese. Both sides of
    every comparison are reduced the same way, so the reduction can only
    forgive punctuation the model re-styled, never invent a word.
    """
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _input_quoted_spans(raw_input):
    """The bodies of the input's quoted spans, in the order the player wrote
    them. The quote vocabulary is the language pack's, so a story written in
    corner brackets has spans too."""
    segments = _ling("_QUOTED_SPAN_RE").split(str(raw_input or ""))
    # split() alternates residue/span/residue...; odd indices are the spans.
    bodies = (_quote_body(s) for i, s in enumerate(segments) if i % 2 == 1)
    return [body for body in bodies if body.strip()]


def _covered_by_spans(atoms, spans):
    """Can this text be read off those spans, in order, in unbroken runs?

    Each span contributes at most one run and the spans are consumed in the
    order they were written, so a line that reorders the player's speech, that
    breaks a span to skip words inside it and rejoin later, or that carries one
    word from nowhere, is not covered.
    """
    if not atoms:
        return True
    if not spans or len(atoms) > _SPEECH_ANCHOR_MAX_CHARS:
        return False
    failed = set()

    def walk(pos, first):
        # Every step consumes a span, so recursion is bounded by the number of
        # spans rather than by the length of the line.
        if pos >= len(atoms):
            return True
        if (pos, first) in failed:
            return False
        for index in range(first, len(spans)):
            span = spans[index]
            start = span.find(atoms[pos])
            while start != -1:
                run = 0
                while (pos + run < len(atoms) and start + run < len(span)
                       and span[start + run] == atoms[pos + run]):
                    run += 1
                for take in range(run, 0, -1):
                    if walk(pos + take, index + 1):
                        return True
                start = span.find(atoms[pos], start + 1)
        failed.add((pos, first))
        return False

    return walk(0, 0)


def player_speech_anchored(line, raw_input):
    """Is every word of this player speech line the player's own?

    Provenance is COVERAGE, not containment. A player who writes several
    quoted spans separated by narration -- the ordinary way anyone writes a
    turn -- gets one merged `speech` element back from interpret, and that
    merge is a contiguous run of nothing. Measured (15-beat run, the beat whose
    question no character ever answered): the merged line read False against
    the raw input while every span of it read True, so the guard dropped the
    whole line and nulled the speech, and the player's question reached no
    mind. A neighbouring beat whose speech happened to be one unbroken quote
    survived and was answered; that was the entire difference.

    So a line is anchored when it is a contiguous run of the input (the old
    floor, kept whole) or when its characters can be read off the input's
    quoted spans in the order written. Narration BETWEEN the spans is not a
    span and does not anchor anything, and text the model invented matches
    nothing and is still refused.
    """
    atoms = _speech_anchor_atoms(line)
    if not atoms:
        return True
    flat_line = re.sub(r"\s+", " ", str(line or "")).strip().casefold()
    flat_source = re.sub(r"\s+", " ", str(raw_input or "")).strip().casefold()
    if flat_line and flat_line in flat_source:
        return True
    return _covered_by_spans(
        atoms,
        [_speech_anchor_atoms(body) for body in _input_quoted_spans(raw_input)])


def discard_unanchored_player_speech(out, raw_input):
    """Drop exact player lines whose words were not the player's own.

    A description such as ``I explain the warning signs`` does not authorize
    the interpreter to write a speech for the player. Downstream ownership
    checks trust the interpreter, so provenance has to be enforced here.
    `player_speech_anchored` is the test, and it is span-aware: merging the
    input's quoted spans into one line is legitimate authorship, inventing
    words is not.
    """
    if not isinstance(out, dict):
        return []

    dropped, kept = [], []
    for event in out.get("sequence") or []:
        if not isinstance(event, dict) or event.get("type") != "speech":
            kept.append(event)
            continue
        line = str(event.get("text") or "").strip()
        if line and not player_speech_anchored(line, raw_input):
            dropped.append(line)
            continue
        kept.append(event)
    out["sequence"] = kept

    flat = str(out.get("speech") or "").strip()
    if flat and not player_speech_anchored(flat, raw_input):
        if flat not in dropped:
            dropped.append(flat)
        out["speech"] = None
    surviving = [event.get("text") for event in kept
                 if isinstance(event, dict) and event.get("type") == "speech"
                 and event.get("text")]
    if surviving:
        out["speech"] = surviving[0]
    return dropped


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
    handles (same tolerance character_room/canonicalize_positions apply).

    FAILS CLOSED. When the handles cannot be enumerated at all, every name,
    uid and alias form is gone and only the numeric-id form is left, so a
    name-authored exclusion matches nothing and this used to answer "not
    excluded" -- delivering the concealed line to the one mind it named. An
    exclusion the engine cannot resolve is not an exclusion that does not
    apply: unresolved, this guard cannot show the observer is NOT the
    excluded party, and withholding one line costs a delivery while
    delivering it costs the firewall. Reported rather than swallowed,
    because a subtraction nothing announces is the next invisible defect."""
    if not conceal_from:
        return False
    id_forms = {str(observer_id).strip()}
    try:
        keys = {k.casefold() for k in character_scene_keys(observer_sheet)}
    except Exception as exc:
        note_step_warning(
            f"conceal_from could not be resolved against observer "
            f"{observer_id!r} ({type(exc).__name__}: {exc}); treating the "
            f"line as concealed from them.")
        return True
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

#: Every key a character's result can carry, classified by how TWO of that
#: character's declarations in one beat combine -- a later micro-round over an
#: earlier one (`loops._speak`), or the action result over the reaction result
#: (`commit_memory`'s `own_result`).
#:
#: CLASSIFYING A KEY IS MANDATORY, because the merge starts from `new` alone:
#: a key the earlier result carries and the later one omits is simply gone,
#: and "omits" is the ORDINARY shape of "had nothing to add this round" --
#: models emit sparse dicts and `_dump` uses exclude_none. Nothing warns,
#: because a field's warnings live inside the branch the drop skips: the only
#: reader of `drive_shift` is `elif own_result.get("drive_shift")` in
#: commit_memory, so a dropped rupture proposal is silent by construction.
#: `project_ops` and `drive_shift` were each lost this way before being named
#: here. tests/test_character_result_merge.py checks these four tuples against
#: CharacterOutput's own field list, so the next field added to the schema has
#: to be classified rather than defaulting to latest-wins by omission.

#: Concatenated in beat order and NOT deduped: two rounds may legitimately
#: carry the same line or motion, and a character who repeats themselves said
#: it twice.
_MERGE_APPEND_FIELDS = ("sequence",)

#: Unioned, order-preserving, exact duplicates dropped (a re-emitted identical
#: update across rounds). Each entry is an independent piece of work, so no
#: round's declared behavior or inference is lost.
_MERGE_UNION_FIELDS = (
    "mind_model_updates",
    "relationship_updates",
    "stance_updates",
    "inference_updates",
    "intent_ops",
    # A project adopted in round 0 and not restated in round 1 was
    # dropped here, which is the reaction-loop drop in miniature and
    # inside a single loop. Projects are removed only by being satisfied
    # or disputed -- never by a later round forgetting to mention one.
    "project_ops",
    "belief_updates",
    "association_updates",
    "present_evidence_used",
    "memory_evidence_used",
    "observations_used",
    "remember_lines",
    "memory_disputes",
    "memory_effects",
    "contact_ops",
    "material_effects",
)

#: Preserved when the later declaration is SILENT about them; a later explicit
#: value wins. These are single-slot decisions -- there is no list to
#: accumulate into -- and saying nothing about one is not retracting it.
_MERGE_PRESERVE_FIELDS = (
    "active_state",
    "ponder",
    # No-op/null means preserve the prior micro-round's explicit decision;
    # start/stop are both truthy dicts and the later explicit one wins.
    "follow_op",
    # PRESERVED rather than unioned because the slot holds exactly one:
    # affect.validate_drive_shift takes a single proposal, and a break closes
    # the window (commit_memory sets rupture=None), so a second proposal in
    # the same beat could not apply even if it were kept. Preserving matters
    # more here than anywhere else on this list: the window is engine-opened,
    # three turns wide, and the shift is invited only inside it, so the one
    # round that answers IS the rupture -- dropping it loses the scar, the
    # former-drive entry and the memory of the break together, and loses them
    # without a warning, since every drive_shift warning is emitted inside the
    # branch the drop skips.
    "drive_shift",
    # Set only when true, by the character stage, when this round's move
    # repeated an earlier one; it tells affect.apply_intent_ops not to credit
    # a `progress` claim. STICKY, because the intent_ops it guards accumulate:
    # latest-wins let a barren round's progress claim ride into commit under a
    # later clean round's flag. Over-suppressing costs one progress tick;
    # laundering credits a goal for a move already made.
    "_barren_beat",
)

#: LATEST WINS, deliberately -- named rather than omitted so the guard can
#: tell a decision from an oversight.
_MERGE_LATEST_WINS_FIELDS = (
    # The latest round's deliberation about the latest round's decision.
    "appraisal",
    "considered_responses",
    "response_candidates",
    "interaction",
    "salience",
    "manifest",
    # Mirrors `_sync_sequence_mirrors` derives FROM `sequence`, which
    # accumulates. They are stale after a merge, and that is safe only because
    # every reader prefers the sequence and falls back to the mirror when
    # there is none (`character._speech_texts`).
    "speech",
    "speech_volume",
    "action",
    "actions",
    # The character stage folds the earlier round's probe into the later one
    # itself, precisely because this merge keeps the latest ("the last round's
    # probe must therefore tell the whole beat's story", character.py).
    "unbidden_probe",
    # Identity of the character both results belong to; equal by construction.
    "name",
    "char_id",
)

#: Result keys that are NOT CharacterOutput fields: written by the stage after
#: validation (`norm_sequence` -> ponder, `_sync_sequence_mirrors` ->
#: speech_volume, `character_step` -> name/char_id/unbidden_probe/
#: _barren_beat) or legacy inputs commit still reads (stance_updates,
#: inference_updates). Enumerated so the guard can insist an unrecognised name
#: is either a schema field or a deliberate extra.
_MERGE_NON_SCHEMA_KEYS = frozenset({
    "stance_updates", "inference_updates", "ponder", "speech_volume",
    "name", "char_id", "unbidden_probe", "_barren_beat",
})


def _merge_character_results(existing, new):
    """Combine a character's earlier-round result with a later one instead of
    overwriting. A character who speaks in more than one micro-round would
    otherwise lose its round-0 sequence/mind_model_updates/etc. at commit,
    which reads ctx.character_results[id] as a single result.

    Which key does what is declared in the four tables above -- append, union,
    preserve-if-the-later-round-is-silent, latest-wins -- and every key a
    result can carry sits in exactly one of them. Read the note above
    `_MERGE_APPEND_FIELDS` before adding a field: an unclassified key is
    latest-wins by accident, and drops without a warning."""
    if not isinstance(existing, dict):
        return new
    if not isinstance(new, dict):
        return existing
    merged = dict(new)
    for field in _MERGE_APPEND_FIELDS:
        merged[field] = _list(existing.get(field)) + _list(new.get(field))
    for field in _MERGE_UNION_FIELDS:
        combined = _concat_dedup(existing.get(field), new.get(field))
        if combined or field in existing or field in new:
            merged[field] = combined
    for field in _MERGE_PRESERVE_FIELDS:
        if not new.get(field) and existing.get(field):
            merged[field] = existing.get(field)
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

# Entity fields that exist so CODE can resolve a reference, not because an
# observer could perceive them. See _perceptible_entities.
_ENTITY_LOOKUP_ONLY_FIELDS = ("aliases",)


def _beneath_visible():
    """Whether what is under someone's clothing is spelled out at all.

    Off unless the host turns it on. What a card authors per region as
    `beneath` is explicit body description, and a default that starts
    narrating it the first time a coat comes off is not a default anyone
    chose. With this off the region still reports itself as bare -- the
    exposure is objective and the story needs it -- and the body's own
    appearance is what fills the rest, which is where it lived before regions
    existed.
    """
    return str(get_setting("attire_beneath") or "").strip().casefold() in (
        "1", "on", "true", "yes")


def attire_view(entry, body=""):
    """One body's clothing as a stage should see it.

    The flat `wearing`/`state` pair stays, because that is the shape the
    Director writes back in `attire:{name:{add,remove,...}}`. Alongside it goes
    one line per region, which is the only representation that can say a robe
    is open rather than merely present -- and the only one that can say a
    region is bare while the body is still dressed.
    """
    if not isinstance(entry, dict):
        return {}
    # Through `rederive_entry`, not straight off the stored dict. `wearing` and
    # `state` used to be passed through verbatim while only `regions` was
    # normalised, so this view could -- and did -- hand a character a coherent
    # region breakdown next to a flat list contradicting it. Live in chat 52:
    # the regions were clean and `wearing` still read
    # `[... 'corset', 'worn', 'skirt']`, with a phantom garment named after a
    # state, because every repair to the ledger's normalisation was bypassed
    # for exactly the two fields anyone reads first.
    #
    # A read path, so this presents the three representations agreeing without
    # writing anything back; commit still owns the stored shape.
    coherent = attire_model.rederive_entry(entry)
    regions = coherent.get("regions") or {}
    lines = attire_model.describe(
        regions, beneath_visible=_beneath_visible(), body=body)
    exposed = attire_model.exposed_regions(regions)
    partial = attire_model.partially_exposed_regions(regions)
    return {
        "wearing": coherent.get("wearing") or [],
        "state": coherent.get("state") or [],
        **({"regions": lines} if lines else {}),
        # Stated rather than left to be worked out from the lines above. What
        # a body shows is exactly this list -- a garment that is loosened or
        # hanging open is still ON, and a region nobody has mentioned is
        # unmodelled rather than bare, so neither appears here.
        **({"exposed": exposed} if exposed else {}),
        **({"partially_exposed": partial} if partial else {}),
    }


def attire_exposure_facts(sc, bodies):
    """Which regions the ledger still has COVERED, per body, for the screen.

    `bodies` is [(ledger_key, [ownership token, ...])] and the CALLER decides
    who is in it -- this function has no perception opinion, the same division
    `_position_delta_payload` keeps for rooms.

    A partially exposed region is left OUT: a garment worn open still counts
    as concealing, so prose calling that region bare is defensible and
    warning about it would spend a rewrite on a true sentence.
    """
    out, ledger = [], (sc or {}).get("attire") or {}
    for key, refs in bodies or ():
        entry = ledger.get(key)
        refs = [str(r).strip() for r in (refs or ()) if str(r).strip()]
        if not isinstance(entry, dict) or not refs:
            continue
        regions = (attire_model.rederive_entry(entry) or {}).get("regions") or {}
        partial = set(attire_model.partially_exposed_regions(regions))
        covered = [r for r in attire_model.covered_regions(regions)
                   if r not in partial]
        if covered:
            out.append({"refs": refs, "covered": covered})
    return out


def exposure_owner_refs(narration_person, display, pronouns=None):
    """Every word in prose that would OWN this body's regions.

    The possessive that means "the player" is decided by narration person,
    not by the persona's pronouns, which is why the person table is language
    data beside the exposure vocabulary rather than a constant here.
    """
    shape = _ling("_EXPOSURE_STATE")
    refs = list((shape.get("person_possessive") or {}).get(
        str(narration_person or "").strip().lower()) or ())
    display = str(display or "").strip()
    if display:
        refs.append(display + "'s")
    poss = str((pronouns or {}).get("possessive") or "").strip()
    if poss:
        refs.append(poss)
    return refs


def scene_attire_view(sc):
    """`attire_view` across every body in the scene."""
    return {
        name: attire_view(entry)
        for name, entry in (sc.get("attire") or {}).items()
        if isinstance(entry, dict)
    }


# How much of a garment's appearance rides in a payload. The Director is the
# only path by which what a thing looks like reaches prose, so it gets enough
# to describe with; a character looking at their own clothes gets the same,
# because a body knows what it is wearing.
ATTIRE_LOOK_CHARS = 60


def compact_attire(entry, look=ATTIRE_LOOK_CHARS):
    """One body's clothing as a single line -- see `attire.compact_line`.

    Replaces the multi-field `attire_view` in PAYLOADS only. Measured on chat
    67: the view sent to the Director was 3,789 chars, this is 1,314 -- 65%,
    ~618 tokens off every resolve call. `attire_view` itself stays as it is for
    panels and anything that wants the structured shape.

    Rederived rather than read raw, for the reason `attire_view` gives: the
    stored `wearing`/`state` pair and `regions` could disagree, and this must
    render the reconciled truth. It is also what migrates a LEGACY body -- a
    story whose attire predates regions entirely -- into regions on read, so
    an old chat needs no backfill to be rendered by this.
    """
    if not isinstance(entry, dict):
        return ""
    regions = (attire_model.rederive_entry(entry) or {}).get("regions") or {}
    return attire_model.compact_line(
        regions, beneath_visible=_beneath_visible(), look=look)


def scene_compact_attire(sc, look=ATTIRE_LOOK_CHARS):
    """`compact_attire` across every body in the scene."""
    return {
        name: compact_attire(entry, look=look)
        for name, entry in (sc.get("attire") or {}).items()
        if isinstance(entry, dict)
    }


def extra_part_phrase(part):
    """One authored extra body part as a deterministic phrase.

    `tail — emerges from the back of the waist; passes through clothing;
    long and russet-furred`. Same input, same string, every beat: the parts
    are card configuration, so a body whose anatomy did not change renders
    byte-identically and a provider's prefix cache can absorb it.
    """
    part = part if isinstance(part, dict) else {}
    kind = " ".join(str(part.get("kind") or "").split())
    if not kind:
        return ""
    try:
        count = max(1, int(part.get("count", 1)))
    except (TypeError, ValueError):
        count = 1
    at = str(part.get("at") or "torso")
    aspect = str(part.get("aspect") or "back")
    if aspect == "sides":
        where = f"across both sides of the {at}"
    elif aspect in ("left", "right"):
        where = f"from the {aspect} side of the {at}"
    else:
        where = f"from the {aspect} of the {at}"
    head = kind if count == 1 else f"{kind} x{count}"
    bits = [f"emerges {where}" if count == 1 else f"emerge {where}"]
    if part.get("through_clothing", True):
        bits.append("passes through clothing worn there"
                    if count == 1 else "pass through clothing worn there")
    else:
        bits.append("worn beneath clothing there")
    description = " ".join(str(part.get("description") or "").split())
    if description:
        bits.append(description)
    return f"{head} — {'; '.join(bits)}"


def extra_parts_lines(parts):
    """Every declared part as its phrase; [] stays [] so defaults stay inert."""
    out = []
    for part in (parts or []):
        text = extra_part_phrase(part)
        if text:
            out.append(text)
    return out


def scene_extra_parts(cast, persona=None, player_name=None):
    """{display name: authored extra parts} for every body that has any.

    Read live from the cards (the acuity/lexicon pattern): no scene state, no
    per-beat maintenance, and a sheet edit fixes the body it describes. Only
    bodies with a non-empty declaration appear, so a cast with none produces
    {} and every payload key hanging off this stays absent.
    """
    out = {}
    for row in (cast or []):
        try:
            sh, _, _ = sheet_state(row)
        except Exception:
            continue
        parts = character_extra_parts(sh)
        if parts:
            out[character_name(sh)] = parts
    if persona is not None:
        parts = persona_extra_parts(persona)
        if parts:
            name = str(player_name or persona.get("name")
                       or persona_name(persona))
            out[name] = parts
    return out


def region_visibility(sc, observer, body, entry=None):
    """Which of one body's regions THIS observer can see, and what conceals
    the rest -- concealment, applied to bodies instead of acts.

    Returns every region in `attire.REGIONS`, in anatomical order, in the
    vocabulary concealed action already uses:

        {"torso": {"visibility": "concealed", "by": {"garments": ["kimono"]}},
         "hands": {"visibility": "overt"},
         ...}

    `by` is a one-key dict naming the KIND of concealer alongside the
    concealers themselves, and the kinds are exactly the three the engine can
    already answer for:

      - `garments` -- what `attire.concealing_garments` says still covers the
        region. A garment that only attaches never appears here: a hair clip
        is present without covering.
      - `containment` -- the body is shut inside something the observer is
        outside (or the observer is shut inside something themselves), read
        through `hiding_holders_of`/`containment_conceals` so the parented
        interior-room form conceals exactly as the `contained` ledger form
        does.
      - `vantage` -- the observer's own position is what fails: the body is in
        their rear arc (`entity_arc`, the `behind_sources` rule -- no NEW
        visual detail from a blind spot), or `visual_level_between` answers
        `none`/`shapes` for darkness, barriers, or distance. At `shapes` a
        silhouette shows presence and outline, not what is worn or bare, so
        every region is concealed -- the same reading `_co_present_company`
        gives an unrecognised figure.

    DERIVED, NEVER STORED. `wearing`/`state`/`regions` are already three
    representations of one wardrobe and they drifted until `rederive_entry`
    existed; a stored per-region `visible` flag would be a fourth with the
    same failure mode and no new information. This is a pure read: the
    coverage half comes from the reconciled regions (which also migrates a
    legacy flat-list body on read), the observer half from the scene, and
    nothing is written anywhere.

    Per-observer on purpose -- the point of the transfer from `conceal_from`.
    Two observers of one body get different answers when one stands behind it,
    or outside the wardrobe it is hiding in. A body is never concealed from
    itself by containment or vantage (`same_subject`, not `==` -- a being
    routinely carries a display name and an entity id at once): a perceiver is
    never sealed from themselves and is never in their own blind spot. Their
    own garments still conceal their regions, because covered is covered.

    Safe-closed: an observer the scene cannot place sees nothing, which is the
    same answer every other spatial query gives for `unknown`.
    """
    sc = sc if isinstance(sc, dict) else {}
    if entry is None:
        ledger = sc.get("attire") or {}
        entry = ledger.get(body)
        if entry is None:
            key = str(body or "").strip().casefold()
            entry = next((value for name, value in ledger.items()
                          if str(name).strip().casefold() == key), None)
    regions = {}
    if isinstance(entry, dict):
        regions = (attire_model.rederive_entry(entry) or {}).get("regions") or {}
    cover = attire_model.concealing_garments(regions)

    body_level = None
    if not same_subject(sc, observer, body):
        level = visual_level_between(sc, observer, body)
        if level != "full":
            # Attribution only: whether sight fails is spatial's composed
            # answer (light, barriers, containment, crossing grace), never
            # re-derived here where a second copy of that policy would drift.
            if containment_conceals(sc, observer, body):
                holders = (hiding_holders_of(sc, body)
                           or hiding_holders_of(sc, observer))
                body_level = {"containment":
                              [str(holders[0])] if holders else []}
            else:
                body_level = {"vantage": ["seen only in silhouette"
                                          if level == "shapes"
                                          else "out of sight"]}
        elif entity_arc(sc, observer, body) == "rear":
            body_level = {"vantage": ["behind the observer"]}

    out = {}
    for region in attire_model.REGIONS:
        if body_level is not None:
            out[region] = {"visibility": "concealed", "by": dict(body_level)}
        elif region in cover:
            out[region] = {"visibility": "concealed",
                           "by": {"garments": list(cover[region])}}
        else:
            out[region] = {"visibility": "overt"}
    return out


def observer_body_regions(sc, observer, body_labels=None, extra_parts=None):
    """Observer-safe attire/body surfaces for a perception payload.

    ``body_labels`` maps canonical scene subjects to labels already safe for
    this observer (``you``, a recognized name, or an appearance-derived
    descriptor).  Canonical keys are never emitted.  Vantage/containment
    concealment removes a region entirely; garment concealment exposes only
    the garment surface, while an overt region may expose its authored
    ``beneath`` description when the host enabled that feature and a garment
    has actually been removed there.

    A SCALE GAP costs texture, never acquaintance: a body far off this
    observer's own scale keeps every region it would otherwise deliver, and
    each arrives without its authored detail (``detail_resolves_between``).

    ``extra_parts`` maps canonical subjects to their authored structured
    body parts (character_schema.character_extra_parts). A visible part rides
    the body's row as ``parts``, gated by the SAME region_visibility verdicts
    the surfaces use: a body-level concealment (vantage, containment,
    darkness) hides every part; garment concealment at the attachment region
    hides only a part authored as worn beneath the clothing, because the
    default part -- a tail through a skirt -- emerges through what covers its
    root. A body is never concealed from itself: the self row keeps all its
    own parts, tucked ones annotated, matching the self-knowledge floor.
    """
    sc = sc if isinstance(sc, dict) else {}
    labels = dict(body_labels or {str(observer): "you"})
    ledger = sc.get("attire") or {}
    parts_map = extra_parts if isinstance(extra_parts, dict) else {}
    results = []
    for body, label in labels.items():
        folded = str(body or "").strip().casefold()
        entry = ledger.get(body)
        if entry is None:
            entry = next((value for key, value in ledger.items()
                          if str(key).strip().casefold() == folded), None)
        parts = parts_map.get(body)
        if parts is None:
            # One being, one name: the map is keyed by display name and the
            # caller may hold another casing of it.
            parts = next((value for key, value in parts_map.items()
                          if str(key).strip().casefold() == folded), None)
        parts = [p for p in (parts or [])
                 if isinstance(p, dict) and p.get("kind")]
        if not isinstance(entry, dict) and not parts:
            continue
        coherent = (attire_model.rederive_entry(entry) or {}
                    if isinstance(entry, dict) else {})
        regions = coherent.get("regions") or {}
        surfaces = attire_model.perceptible_region_surfaces(
            regions, beneath_visible=_beneath_visible())
        visibility = region_visibility(
            sc, observer, body, entry=coherent if coherent else None)
        # The scale gap is a fact about the PAIR, not about a shoulder, so it
        # is asked once per body rather than once per region.
        resolves = detail_resolves_between(sc, observer, body)
        delivered = {}
        for region in attire_model.REGIONS:
            surface = surfaces.get(region)
            if not surface:
                continue
            verdict = visibility.get(region) or {}
            cause = verdict.get("by") or {}
            if verdict.get("visibility") == "concealed" \
                    and "garments" not in cause:
                continue
            # ACUITY IS PROPORTIONALITY. A region on a body far off this
            # observer's own scale delivers its form and not its texture --
            # the same subtraction dim light already makes, on the axis the
            # `scales` ledger measures. Measured: an observer received
            # "Barely visible copper-gold hair on her shins" and card tan-line
            # detail verbatim across a 4x gap, because nothing between the
            # ledger and the composed view ever read the ledger. It SUBTRACTS
            # only: the region still arrives, still says covered-or-bare,
            # still names the garment. `same_subject` is deliberately not
            # consulted -- a body's ratio to itself is 1.0, so the self row is
            # never coarsened by construction.
            delivered[region] = (
                surface if resolves
                else attire_model.coarsen_region_surface(surface))
        shown_parts = []
        shown_data = []
        self_view = same_subject(sc, observer, body)
        for part in parts:
            # A REGION THIS MAP KNOWS, or nothing is shown.
            #
            # `region_visibility` is keyed by attire.REGIONS. A part authored
            # on a CARD is coerced to those keys (character_schema's
            # `_extra_part_placement`), but a part minted by a
            # `physical_transformation` is model free text and nothing
            # normalised it -- so `at` arrived as "top of the head" and "back
            # of the waist". `.get()` missed, the empty verdict read as NOT
            # concealed, and the guard failed OPEN.
            #
            # Live, chat 76 turn 71: every one of the eight regions correctly
            # returned concealed/vantage "out of sight", and The Doctor still
            # received "Two fox ears emerge from ... Hinami's top of the head"
            # as a SIGHT percept through a closed bathroom door -- into his
            # view, his observations, and his character step's appraisal.
            #
            # Resolve through the same fallback the card path uses, then treat
            # an unresolvable placement as concealed. A guard on the firewall
            # must fail CLOSED: an unknown region is not evidence of exposure,
            # and a missing key must never read as permission.
            at = str(part.get("at") or "").strip().casefold()
            if at not in attire_model.REGIONS:
                at = _extra_part_placement(str(part.get("kind") or ""))[0]
            verdict = visibility.get(at)
            if verdict is None:
                continue
            cause = verdict.get("by") or {}
            concealed = verdict.get("visibility") == "concealed"
            if concealed and "garments" not in cause and not self_view:
                continue   # whole body unseen: vantage/containment/darkness
            tucked = (concealed and "garments" in cause
                      and not part.get("through_clothing", True))
            if tucked and not self_view:
                continue   # worn beneath the clothing that covers its root
            text = extra_part_phrase(part)
            if not text:
                continue
            if tucked:
                text += " [currently beneath clothing]"
            shown_parts.append(text)
            # The phrase is shaped for a payload a model would rewrite. The
            # composer renders straight to the reader, so it needs the parts
            # themselves -- same gating decision, carried structured. Kept
            # beside `parts` rather than replacing it: the phrase is what
            # the Director payloads and this module's own tests consume.
            shown_data.append({**part, "tucked": tucked})
        if delivered or shown_parts:
            row = {"body": str(label or "someone"), "regions": delivered}
            if shown_parts:
                row["parts"] = shown_parts
                row["part_data"] = shown_data
            results.append(row)
    return results


CROWDS_KEY = crowds_model.CROWDS_WORLD_KEY


def crowds_for_room(cid, sc, room_id, inputs=None):
    """What crowds an observer in this room registers, already described.

    A crowd is a thing in a room, so it is delivered per observer and scoped to
    the room they are standing in -- never as a scene-wide list, which would
    hand someone in a back office the state of the square outside.

    It deliberately does NOT go through the managed-presence path. A crowd that
    consumed one of the six `max_managed` slots would have solved nothing,
    which is the whole reason the object exists.

    Density is computed here rather than read, because it is a function of the
    band and the ROOM and the crowd may have walked into a different one since
    it was minted.

    TWO SPECIES SHARE THIS VIEW SHAPE (DESIGN_BACKGROUND_PRESENTATION §B1):
    the authored ledger rows above, and derived charter crowds
    (`charter_crowds_for_room`), appended below under the same fields so the
    composer and every payload read both identically. A derived row differs
    where the derivation says it must: no drift (charter bodies move
    individually on their own errands), no `emerged` list (an emerged body's
    presence record IS the record and membership excludes it at the next
    read), no `talk` (the charter's talk is the chatter seam's, delivered
    beside this view, never twice). ``inputs`` is `chatter_inputs`' shared
    fetch, exactly as `chatter_for_room` takes it.
    """
    if not room_id:
        return []
    # `effective_room_size`, not the raw authored string: an unsized "Great
    # Hall" is `large` for proximity grading and was `medium` here, so
    # `density("a throng", ...)` returned PACKED under one and CRUSH under the
    # other -- and CRUSH is what `terrain` turns into a `membrane` you cannot
    # see across and what `drift` turns into CARRY. One question, one answer.
    size = effective_room_size(sc or {}, room_id)
    out = []
    for crowd in crowds_model.crowds_in_room(wget(cid, CROWDS_KEY, []) or [],
                                             room_id):
        out.append({
            "uid": crowd.get("uid"),
            "what": crowds_model.describe(crowd, size),
            "density": crowds_model.density(crowd.get("band"), size),
            # WHAT A CHANGE IS MEASURED AGAINST, published beside the
            # sentence composed from it. `composer.room_content_percepts`
            # hashed `what` and nothing else, so every re-rendering of an
            # unchanged crowd read as an event and reached the narrator as an
            # obligation (chat 95: seven `changed` verdicts in sixteen turns
            # on a crowd whose band never moved). An authored crowd's
            # composition IS state -- it is a stored field, and it changes
            # only when `crowds.apply_ops` writes it, which is an event.
            "state": (crowds_model.normalize_band(crowd.get("band")),
                      str(crowd.get("composition") or ""),
                      crowds_model.density(crowd.get("band"), size),
                      str(crowd.get("mood") or "")),
            "heading": crowd.get("heading") or None,
            # A crowd is terrain, so the observer is told what kind. `open`
            # is ground with people on it; `membrane` is the barrier word
            # spatial.py already uses for a thing you push through and cannot
            # see across, which is what standing in a packed crowd is.
            "terrain": crowds_model.terrain(crowd.get("band"), size),
            # The press's OFFER, never its verdict: {toward, strength}. The
            # Director decides whether it lands, and if it does it is an
            # arrival that goes through the commit path like any other move.
            "drift": crowds_model.drift(crowd, size),
            # Who is already standing out of it. Delivered so the Director
            # voices the rope-seller it emerged last beat instead of emerging
            # a second one, and so the crowd is not asked to produce a person
            # who is already in front of the player.
            "emerged": list(crowd.get("emerged") or []),
            # What the murmur is ABOUT, when the crowd holds anything --
            # attributed as talk, never to a name. Own-room only by
            # construction: every caller passes the observer's own room, so
            # a crowd seen across an open doorway is a shape and a sound,
            # never words (the zero-content assertion stays zero-content).
            # This is perception of ambient speech, the design's first
            # legitimate door; the durable carried-report copy still moves
            # only through an explicit telling op.
            "talk": crowds_model.talk_view(crowd),
        })
    for crowd in charter_crowds_for_room(cid, sc, room_id, inputs):
        out.append({
            "uid": crowd.get("uid"),
            "what": crowds_model.describe(crowd, size),
            # Density, terrain and drift are the same physics for both
            # species: a press of simulated people is exactly as much a
            # membrane as a press of authored ones. Drift is None by
            # construction (a derived crowd has no heading), spelled through
            # the same function so there is one answer to what drift is.
            "density": crowds_model.density(crowd.get("band"), size),
            # The derived species' state carries no composition, and the
            # reason is not the species: `charter_crowd.composition_of` is
            # recomputed at every read as the top two of a tally over a
            # membership that moves individually by design, so it reorders
            # without the crowd changing. Measured, chat 95: five spellings
            # of one unchanged fact over sixteen turns ("a dozen or so
            # captains and commanders", "...commanders and lieutenant
            # commanders", "...lieutenant commanders and commanders"), and a
            # sorted set of the nouns still flips four times. The band is the
            # coarse summary of that same membership and it is what carries a
            # real change here -- `crowd_for` already says so ("the
            # membership count dies here: it met the band vocabulary").
            "state": (crowds_model.normalize_band(crowd.get("band")),
                      crowds_model.density(crowd.get("band"), size),
                      str(crowd.get("mood") or "")),
            "heading": None,
            "terrain": crowds_model.terrain(crowd.get("band"), size),
            "drift": crowds_model.drift(crowd, size),
            "emerged": [],
            "talk": [],
            # Recognisable twice over -- the uid prefix is the enforcement
            # (`crowds.apply_ops` refuses these), the flag is the courtesy.
            "derived": True,
        })
    return out


def chatter_inputs(cid, sc, turn_idx=None):
    """Everything ambient chatter reads, fetched once per perception stage —
    and, since Part B, everything the derived charter crowd reads too
    (`charter_crowds_for_room` shares this fetch under its own memo), so a
    stage pays the registry deepcopy once however many seams consume it.

    `charter_runtime.registry_for` normalizes the whole registry (measured
    21.8ms with its deepcopy on one 40-body charter), so a per-perceiver
    fetch would multiply that by the cast; the stage fetches once, every
    `chatter_for_room` call reuses the slices, and a per-room memo makes the
    co-located cast free. Presence records are read here too, and carry two
    different claims that must not collapse into one (Part C's §C3 split):
    `known_bodies` is RECOGNITION — a charter body somebody has met is
    somebody chatter attribution may name (§A2c), and a name once learned is
    never unlearned — while `presented_bodies` is PRESENTATION — the bodies
    a record still presents individually this beat, which lapses after
    `charter_crowd.PRESENTED_IDLE_BEATS` idle beats so the body returns to
    the derived crowd's ground. ``turn_idx`` is what ages the second set; a
    caller without one gets the conservative no-lapse read.
    """
    from world.charter_crowd import presented
    from world.charter_runtime import cached_registry

    # Through `cached_registry`, NOT `registry_for(cid)`: the registry key
    # is frame-scoped and `registry_for`'s default pins the PRESENT era
    # explicitly, while every sibling read on this seam (`crowds`,
    # `background_presences`) follows the pipeline's ambient active frame —
    # a flashback's observer must hear the flashback's charters. The cached
    # object is shared and read-only; this function only slices it.
    try:
        registry = cached_registry(cid)
    except Exception:
        registry = {"items": {}}
    known_refs = {}
    presented_refs = {}
    for rec in (wget(cid, "background_presences", {}) or {}).values():
        if not isinstance(rec, dict):
            continue
        live = turn_idx is None or presented(rec, turn_idx)
        for ref in rec.get("charter_refs") or []:
            if isinstance(ref, dict):
                known_refs.setdefault(
                    str(ref.get("charter") or ""), set()).add(
                    str(ref.get("body") or ""))
                if live:
                    presented_refs.setdefault(
                        str(ref.get("charter") or ""), set()).add(
                        str(ref.get("body") or ""))
    charters = []
    for key, item in sorted((registry.get("items") or {}).items()):
        state = (item or {}).get("state") or {}
        charters.append({
            "key": str(key),
            "bodies": state.get("bodies") or {},
            "watch": state.get("watch") or {},
            "posts": state.get("posts") or {},
            "naming": state.get("naming"),
            "figures": state.get("figures") or {},
            "window_acts": state.get("window_acts") or [],
            "clock_hours": float(state.get("clock_hours") or 0.0),
            "known_bodies": frozenset(known_refs.get(str(key), ())),
            "presented_bodies": frozenset(presented_refs.get(str(key), ())),
            # The two slices the derived crowd adds to chatter's read
            # (`charter_crowds_for_room` shares this fetch): who is bound to
            # a registered character, and what everyone is carrying.
            "bindings": frozenset(
                str(k) for k in (state.get("bindings") or {})),
            "feel": state.get("feel") or {},
        })
    return {"charters": charters, "memo": {}}


def charter_crowds_for_room(cid, sc, room_id, inputs=None):
    """The derived charter crowds standing in one room: stored-shape rows,
    computed from the registry and NEVER persisted.

    DESIGN_BACKGROUND_PRESENTATION Part B: the registry bodies whose place
    is this room, minus everyone individually presented (bound bodies,
    bodies with a live presence record), projected through
    `world.charter_crowd.crowd_for`. Derived at every read, so it cannot
    drift from where `charter_move.errands` actually walked people -- the
    second-source-of-truth scar `world/crowds.py` is written after.

    Shares `chatter_inputs`' once-per-stage registry fetch and adds a
    per-room memo, exactly as `chatter_for_room` does; `persist/commit.py`
    calls this too, to resolve an `emerge` against the same rows perception
    showed, because with nothing stored the only way two readers agree is
    to be the same reader.
    """
    from world import charter_crowd

    if not room_id:
        return []
    inputs = inputs if isinstance(inputs, dict) else chatter_inputs(cid, sc)
    memo = inputs.setdefault("crowd_memo", {})
    room = str(room_id)
    if room in memo:
        return [dict(row) for row in memo[room]]
    rows = []
    for charter in inputs.get("charters") or []:
        crowd = charter_crowd.crowd_for(cid, charter, room)
        if crowd is not None:
            rows.append(crowd)
    rows = rows[:charter_crowd.CO_LOCATED_CAP]
    memo[room] = rows
    return [dict(row) for row in rows]


def presence_figures_for_room(cid, sc, room_id, inputs=None, *,
                              turn_idx=None, frame_id=None):
    """The unregistered bodies standing in this room that no crowd carries.

    DESIGN_BACKGROUND_PRESENTATION B2 has two clauses and only one of them
    was ever built. The clause that was: "a charter body is ground (in the
    crowd) exactly when nothing this beat presents it individually" --
    `charter_crowd.members_of` SUBTRACTS bound bodies and bodies with a live
    presence record. The clause that was not: "below the floor of the
    smallest band, members present as individual ambient figures through the
    existing overlay path", and, implicitly, that the bodies the first
    clause subtracts are presented SOMEWHERE. They were not. Perception
    builds every observer's co-present body list out of the cast and the
    players, so a body the crowd let go of entered no view at all.

    Measured live 2026-08-28, chat 98 turns 10-13: five crew whose charter
    `place` was the player's lounge read as "a handful lieutenant commanders
    and ensigns" until each acquired a presence record, at which point
    `crowds_for_room` returned `[]` and the room held nobody in any view --
    while `background_presence_records` still returned all five. A
    subtraction whose matching addition does not exist does not move a
    person from one presentation to another; it deletes them.

    Two species, one shape, exactly complementary to `crowds_for_room`:

    * every durable `background_presences` record `presence_room` puts in
      this room -- the same resolver the voice gate and the background stage
      use, so a presence is not in one room for being seen and another for
      being spoken to. `presence_has_an_identity` is the personhood floor,
      borrowed rather than restated: it is already the predicate that
      decides a tracked name is a person's to withhold, and a ceiling-
      mounted suppression fixture with an accrued record is not somebody
      standing there (chat 82 t1, where one rendered as "the unfamiliar
      person" in the room's own description);
    * every charter body derived at this place whose institution holds too
      few here to be a crowd. At or above `CHARTER_CROWD_FLOOR` the crowd IS
      the presentation and the body must not arrive twice -- including when
      `charter_crowds_for_room`'s `CO_LOCATED_CAP` drops that crowd from the
      view, because the cap decides how many crowds a room shows, never
      whether an institution's people are ground.

    The bound is the room and nothing else: at most
    ``CHARTER_CROWD_FLOOR - 1`` bodies per co-located institution (two, with
    today's floor of three), plus the ledger rows already standing here --
    the same ledger `_composer_identity_space` and the Director's
    `addressable_presences` read whole. Callers scope the ROOMS
    (perception passes the rooms its perceivers stand in), which is what
    keeps a 300-body institution from deriving 300 figures for a back
    office.

    Rows are the co-present body shape: ``name``, ``room``, ``appearance``,
    ``role`` -- the last being the institution's own public noun for the
    body, kept beside the summary because a minted display name carries it
    in front of the personal name and the identity strip would otherwise
    subtract the whole description (`_unknown_actor_label`).
    ``inputs`` is `chatter_inputs`' shared per-stage fetch, memoized per room
    exactly as `charter_crowds_for_room` and `chatter_for_room` are.
    """
    from persist.commit import (presence_has_an_identity, presence_name_items,
                                presence_room)
    from world import charter_crowd

    if not room_id:
        return []
    inputs = (inputs if isinstance(inputs, dict)
              else chatter_inputs(cid, sc, turn_idx=turn_idx))
    memo = inputs.setdefault("figure_memo", {})
    room = str(room_id)
    if room in memo:
        return [dict(row) for row in memo[room]]

    # One ledger read per stage, not per room -- the same discipline
    # `chatter_inputs` applies to the registry.
    ledger = inputs.get("presence_ledger")
    if ledger is None:
        ledger = inputs["presence_ledger"] = (
            wget(cid, "background_presences", {}) or {})

    # Whom the derived crowds carry, by charter body key -- FIRST, because
    # it decides both loops below. Recomputed from the same slices
    # `charter_crowds_for_room` projects, so the two answers cannot disagree
    # about who is ground. A record whose presentation has LAPSED (§C3's
    # idle beats) puts its body back in the crowd, and that body must not
    # then arrive here as well: the ledger row still exists, and its history
    # is exactly what lapsing declines to delete.
    by_key = {}
    carried = set()
    for charter in inputs.get("charters") or []:
        key = str(charter.get("key") or "")
        by_key[key] = charter
        members = charter_crowd.members_of(charter, room)
        if len(members) >= charter_crowd.CHARTER_CROWD_FLOOR:
            carried.update((key, member) for member in members)

    def _refs_of(record):
        return {(str(r.get("charter") or ""), str(r.get("body") or ""))
                for r in ((record or {}).get("charter_refs") or [])
                if isinstance(r, dict)}

    def _noun_for(refs):
        """What the body IS, on the same terms the crowd's composition says
        it -- a rank or a duty is worn, and an observer in the room reads it
        off the same band these people are members of. Computed only for the
        bodies actually emitted, so a plaza's crowd costs nothing here."""
        for charter_key, body_key in sorted(refs):
            noun = charter_crowd.member_noun(
                by_key.get(charter_key) or {}, body_key)
            if noun:
                return noun
        return ""

    rows, seen, seen_refs = [], set(), set()
    for name, rec in presence_name_items(ledger):
        name = str(name or "").strip()
        if not name or name.casefold() in seen:
            continue
        if presence_room(sc, name, rec) != room:
            continue
        if not presence_has_an_identity(sc, name, rec):
            continue
        refs = _refs_of(rec)
        if refs & carried:
            continue
        seen.add(name.casefold())
        seen_refs |= refs
        rows.append({
            "name": name, "room": room,
            "appearance": (str(((rec or {}).get("sketch") or {}).get(
                "appearance") or "") or _noun_for(refs)),
            "role": _noun_for(refs),
        })

    try:
        from world.charter_runtime import background_presence_records
        derived = background_presence_records(
            cid, places={room}, frame_id=frame_id)
    except Exception:
        derived = {}
    for name, record in sorted(derived.items()):
        refs = _refs_of(record)
        if str(name).casefold() in seen or (refs & seen_refs) or (refs & carried):
            continue
        seen.add(str(name).casefold())
        rows.append({"name": str(name), "room": room,
                     "appearance": _noun_for(refs), "role": _noun_for(refs)})
    memo[room] = rows
    return [dict(row) for row in rows]


def present_charter_figures(cid, sc, rooms, frame_id=None):
    """Every unpromoted charter body standing in `rooms`, with the post it
    holds -- the DIRECTOR's view of who is already here.

    `presence_figures_for_room` is the PERCEPTION view and subtracts the
    bodies a derived crowd carries, because a room's crowd is their
    presentation there. The Director is not a perceiver: it owns what
    exists, and what it needs to know before minting "the innkeeper" is
    that three innkeepers hold that post in this room whether a crowd
    presents them or not. Measured, Harrowmere: ten Director-minted people
    over forty turns, eight of them a second copy of a charter post-holder
    standing in the room -- a clerk beside three clerks, an innkeeper
    beside three, a reeve minted under the ledgered reeve's own name --
    because the resolve payload showed the durable presence ledger (who
    has EARNED a record) and never the derived bodies (who is HERE).

    Rows: ``name`` (the display name every other seam speaks), ``room``,
    ``role`` (the institution's public noun for the post held, or "" for
    a member holding no post this window), ``posts`` (the post ids on
    watch), ``charter`` and ``body`` (the permanent identity a binding
    keys on). Posted bodies first, then members, then by name, so a capped
    payload keeps the people a role could be mistaken for.
    """
    from world import charter_crowd

    places = {str(r) for r in (rooms or ()) if str(r or "")}
    if not places:
        return []
    try:
        from world.charter_runtime import background_presence_records
        derived = background_presence_records(
            cid, places=places, frame_id=frame_id)
    except Exception:
        return []
    rows = []
    for name, record in derived.items():
        refs = [r for r in (record.get("charter_refs") or [])
                if isinstance(r, dict)]
        ref = refs[0] if refs else {}
        hint = str(((record or {}).get("sketch") or {}).get("role_hint") or "")
        posts = ([] if hint.startswith("member of ")
                 else [p.strip() for p in hint.split(",") if p.strip()])
        role = ""
        for post in posts:
            role = charter_crowd._role_noun(post)
            if role:
                break
        rows.append({
            "name": str(name),
            "room": str(((record or {}).get("sketch") or {})
                        .get("station_room") or ""),
            "role": role,
            "posts": posts,
            "charter": str(ref.get("charter") or ""),
            "body": str(ref.get("body") or ""),
            # Where this body sleeps (`charter_dwellings` says which rooms
            # that makes private).
            "home": str(((record or {}).get("sketch") or {})
                        .get("home_room") or ""),
        })
    rows.sort(key=lambda r: (0 if r["posts"] else 1, r["name"].casefold()))
    return rows


def dwellings_in_reach(cid, rooms, frame_id=None):
    """`charter_dwellings` for the Director's payload: the rooms in reach
    that are somebody's home, who lives there and who is in. Empty for a
    story with no charter, so an ordinary payload is unchanged."""
    try:
        from world.charter_runtime import charter_dwellings
        return charter_dwellings(cid, rooms, frame_id=frame_id)
    except Exception:
        return []


def chatter_for_room(cid, sc, room_id, inputs=None):
    """What an observer in this room hears of the crowd's talk: a hum band
    as ground, and at most one overheard fragment as figure.

    DESIGN_BACKGROUND_PRESENTATION Part A, delivered exactly where the crowd
    view is (`crowds_for_room`) and for the same reason: every caller passes
    the observer's own room, so admission is decided at the seam that
    already decides what a bystander takes in, and
    `composer.observations_from_render` then makes character receipt
    legitimate with no second representation. The fragment is the TRIPLE —
    speaker/act/other/subject labels — never the substrate's template line;
    the engine holds no sentence content, so none can cross.

    Deterministic and seeded from persisted state only (chat, room, each
    charter's own clock), so a replay renders the identical murmur.
    """
    from world import charter_chatter

    if not room_id:
        return []
    inputs = inputs if isinstance(inputs, dict) else chatter_inputs(cid, sc)
    memo = inputs.setdefault("memo", {})
    room = str(room_id)
    if room in memo:
        return [dict(e) for e in memo[room]]

    size = effective_room_size(sc or {}, room)
    crowds = crowds_model.crowds_in_room(wget(cid, CROWDS_KEY, []) or [],
                                         room)
    # BOTH species feed the band floor and the density inversion (§A2a's
    # "graded against the crowd band already present", §A2d's table): a
    # derived charter crowd IS a crowd standing in the room, and in a
    # charter-only story the authored ledger is empty — reading it alone
    # left a derived throng with no hum floor and a derived crush still
    # admitting ordinary fragments, so degradation did not invert for the
    # exact species the design is about. One memoized read on the fetch
    # this function already shares with `charter_crowds_for_room`.
    standing = crowds + charter_crowds_for_room(cid, sc, room, inputs)
    band_rank = max((crowds_model.band_rank(c.get("band"))
                     for c in standing), default=0)
    severity = {crowds_model.LOOSE: 0, crowds_model.PACKED: 1,
                crowds_model.CRUSH: 2}
    density = crowds_model.LOOSE
    for crowd in standing:
        packed = crowds_model.density(crowd.get("band"), size)
        if severity[packed] > severity[density]:
            density = packed

    # The beat's entanglement set: whoever the scene itself places in this
    # room, plus anyone stepped out of a crowd here. The one fragment worth
    # hearing is the crowd talking about *you*.
    notable = {str(name) for name, where in
               ((sc or {}).get("positions") or {}).items()
               if str(where or "") == room}
    for crowd in crowds:
        notable.update(str(n) for n in (crowd.get("emerged") or []))

    rows = []
    for charter in inputs.get("charters") or []:
        bodies = charter["bodies"]
        figures = charter["figures"]

        def _name(key, charter=charter, bodies=bodies, figures=figures):
            key = str(key or "")
            if key in figures:
                return key
            body = bodies.get(key)
            return str((body or {}).get("name") or "") if body else ""

        for act in charter_chatter.acts_in_room(charter["window_acts"],
                                                room):
            rows.append({**act, "charter": charter,
                         "other_name": _name(act.get("other")),
                         "subject_name": _name(act.get("subject"))})

    hum = charter_chatter.hum_rank(len(rows), band_rank, density)
    seed_material = "chatter|%s|%s|%s" % (
        cid, room, "|".join("%s@%0.4f" % (c["key"], c["clock_hours"])
                            for c in inputs.get("charters") or []))
    out = []
    phrase = charter_chatter.hum_phrase(hum)
    if phrase:
        out.append({"kind": "hum", "uid": "hum:%s" % room, "what": phrase,
                    "band": charter_chatter.HUM_BANDS[hum]})

    picked = charter_chatter.overheard_fragment(
        rows, notable=notable, density=density, seed_material=seed_material)
    if picked is not None:
        charter = picked["charter"]
        speaker, _ = charter_chatter.participant_label(
            picked.get("actor"), place=room, bodies=charter["bodies"],
            watch=charter["watch"], posts=charter["posts"],
            naming=charter["naming"], figures=charter["figures"],
            known_bodies=charter["known_bodies"])
        other, _ = charter_chatter.participant_label(
            picked.get("other"), place=room, bodies=charter["bodies"],
            watch=charter["watch"], posts=charter["posts"],
            naming=charter["naming"], figures=charter["figures"],
            known_bodies=charter["known_bodies"])
        subject = charter_chatter.subject_label(
            picked.get("subject"), bodies=charter["bodies"],
            figures=charter["figures"], naming=charter["naming"])
        fragment = {"speaker_label": speaker, "act": picked.get("act"),
                    "other_label": other, "subject_label": subject}
        out.append({"kind": "fragment",
                    "uid": charter_chatter.fragment_key(picked),
                    "what": charter_chatter.fragment_phrase(fragment),
                    **fragment})
    memo[room] = out
    return [dict(e) for e in out]


def couriers_for_room(cid, sc, room_id):
    """What couriers an observer in this room registers, already described.

    The perception half of the interception seam: a courier the player could
    never SEE is a courier the player could never stop, and the design's
    verbs -- intercept, follow, question, outrun, silence -- all begin with a
    body in a room noticing another body in it. Scoped to the observer's own
    room like `crowds_for_room`, and for the same reason.

    What crosses is what a bystander could take in: the figure, which door he
    makes for, whether he is waiting. NEVER the message -- a satchel does not
    broadcast its contents, and the report itself moves only through delivery,
    questioning, or seizure, all of which are commit-validated ops.
    """
    from story import couriers as couriers_model

    if not room_id:
        return []
    standing = wget(cid, couriers_model.COURIERS_WORLD_KEY, []) or []
    out = []
    for courier in couriers_model.couriers_in_room(standing, room_id):
        route = [str(r) for r in courier.get("route") or []]
        leg = max(0, int(courier.get("leg") or 0))
        heading = route[leg + 1] if leg + 1 < len(route) else None
        out.append({
            "courier_id": courier.get("uid"),
            "what": couriers_model.courier_voice(courier),
            "heading": heading,
            # Standing at his destination with the message undelivered: a
            # man waiting at a gate, which a beat may greet, rob or watch.
            "waiting": courier.get("status") == couriers_model.ARRIVED,
        })
    for courier in couriers_model.passed_through(standing, room_id):
        route = [str(r) for r in courier.get("route") or []]
        # The door he went out by: the room after THIS one on his route,
        # which is what an observer who watched him cross actually saw.
        try:
            heading = route[route.index(str(room_id)) + 1]
        except (ValueError, IndexError):
            heading = None
        out.append({
            "courier_id": courier.get("uid"),
            "what": "%s, passing through without stopping"
                    % couriers_model.courier_voice(courier),
            "heading": heading,
            "waiting": False,
        })
    return out


def artifacts_for_room(cid, sc, room_id):
    """What posted notices an observer in this room registers.

    The perception half of the reading seam, `couriers_for_room`'s twin: a
    bill nobody can see is a bill nobody can read OR tear down, and both of
    those are commit-validated ops that need the `artifact_id` shown here.

    What crosses is what a glance takes in: that a notice hangs there, and
    what kind of thing it looks like. NEVER the claim and never the wording
    -- from across a square a bill is paper, and its content moves only
    through the explicit `read`, which is what keeps walking past a wall
    from broadcasting it into every mind in the room. A torn-down bill
    shows nothing at all; that silence is the feature.
    """
    from story import artifacts as artifacts_model

    if not room_id:
        return []
    return [{
        "artifact_id": artifact.get("uid"),
        "what": artifacts_model.artifact_voice(artifact),
    } for artifact in artifacts_model.posted_in_room(
        artifacts_model.standing_artifacts(cid), room_id)]


def _subject_spellings(sc, subject):
    """Every handle this scene keys one being by: the string as given, plus
    the entity id and the display name of the record it names.

    A being routinely carries the pair at once -- entity `tardis_001`, display
    name "Blue Police Box" -- and each of its ledgers is keyed by whichever
    handle its writer had. Aliases are deliberately NOT spellings here: they
    are lookup vocabulary, several beings may claim one, and this list decides
    a firewall answer.
    """
    text = str(subject or "").strip()
    if not text:
        return []
    forms = [text]
    seen = {text.casefold()}
    for eid, ent in ((sc or {}).get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        labels = (eid, ent.get("name"), *(ent.get("aliases") or []))
        if not any(str(label or "").strip().casefold() == text.casefold()
                   for label in labels):
            continue
        for handle in (eid, ent.get("name")):
            form = str(handle or "").strip()
            if form and form.casefold() not in seen:
                seen.add(form.casefold())
                forms.append(form)
        break
    return forms


def _enclosure_of(sc, subject):
    """The nearest enclosure around this being, under any name it is keyed by.

    The first spelling the scene knows an enclosure for wins. A spelling the
    scene does not key answers "nothing around it" -- which is the ignorant
    answer, indistinguishable from a body standing in the open -- and the
    informed answer must outrank it.
    """
    for form in _subject_spellings(sc, subject):
        holders = hiding_holders_of(sc, form)
        if holders:
            return str(holders[0]).strip()
    return ""


def _enclosure_conceals(sc, observer, target):
    """`spatial.containment_conceals`, asked under every live spelling.

    Sight and sound need both parties on the same side of every closed thing,
    which `containment_conceals` decides by comparing their nearest
    enclosures -- resolving each from the ONE string it was handed. One being
    routinely answers to two (a cast display name and a scene entity id), each
    ledger is keyed by whichever its writer had, and
    `spatial_identity.canonical_subject_map` deliberately declines to fold a
    lone entity-id key, so the pair stays live on purpose. Handed the spelling
    a scene does not key, the primitive reports a being with nothing shut
    around it, and every caller reads that as "in the open".

    So both parties are resolved across their spellings first, and the two
    enclosures are compared through `same_subject`, because the holder carries
    the pair too. Nothing is concealed from itself under either of its names.
    """
    if same_subject(sc, observer, target):
        return False
    around_observer = _enclosure_of(sc, observer)
    around_target = _enclosure_of(sc, target)
    if around_observer == around_target:
        return False
    return not same_subject(sc, around_observer, around_target)


def _perceptible_entities(sc, perceiver_names=None):
    """The entities dict to serialize into a PERCEPTION payload.

    Perception is handed the objective entity table so it can describe what
    is present -- but an entity carries two kinds of string. Its `name` and
    `description` are what an observer standing there could actually take
    in. Its `aliases` and its dict KEY are lookup handles, written for
    commit.track_background_presences and background._name_to_entity_id to
    match against, and an observer has no way to acquire that vocabulary.

    Handing both to the model let the vocabulary leak. Observed live
    (Elevator Adventure branch 41, turn 91): entity `tardis_001`, display
    name "Blue Police Box", aliases ["tardis", "box", "police box"]. Dr.
    Moon's own view came back "The TARDIS looms behind her, still wheezing
    as its temporal engines wind down" -- a word she has never heard, in
    the same sentence where the man himself was correctly anonymized as
    "the lean energetic man" (identities are scrubbed by
    _scrub_unknown_identities; object vocabulary was not).

    So the lookup handles do not go in: entities are keyed by display name
    where that is unambiguous, and aliases are dropped. A character who
    legitimately knows what the thing is knows it from their own sheet and
    memory -- which is where that knowledge belongs.

    `state` is the SECOND thing this table carries that an observer may have
    no channel to. The Director writes it as objective fact, in act-naming
    language -- `state.posture` and `state.proximity` spell out what a body
    is doing and where it is doing it. Observed live: a body shut inside a
    container had its every act written out in `state` while no perceiver in
    the call had any sight of it at all. That is the same shape as the alias
    leak above -- objective state handed over with an implicit instruction
    not to use it -- and the same argument applies: when NOBODY in this call
    can perceive the entity, none of them has a legitimate use for what it is
    doing, so it does not go in.

    `perceiver_names` is who the payload is being built for. Concealment is
    decided by containment only: an entity in the open is unaffected, so this
    is inert for the ordinary scene and bites exactly on the enclosed case
    that motivated it. The entity still appears -- only `state` is withheld --
    because presence may reach the perceiver through contact or sound even
    when nothing else does. Omitted (the default) keeps the whole table, which
    is right for callers that have no perceiver set to gate against.

    Concealment goes through `_enclosure_conceals`, which asks both parties
    under every spelling they are keyed by: the record's `name` and its dict
    key are routinely two live handles for one being, and a gate that resolves
    only one of them failed OPEN here for an id-keyed enclosed entity (its
    act-naming `state` shipped to every perceiver) and CLOSED for an id-keyed
    co-occupant (denied what the body beside it was doing).
    """
    entities = (sc or {}).get("entities") or {}
    if not isinstance(entities, dict):
        return entities

    names = [str(n).strip() for n in (perceiver_names or []) if str(n or "").strip()]
    _inhabited_by_a_perceiver = {
        holder for holder in (_body_interior_holder(sc, n) for n in names)
        if holder
    }

    def _state_reaches_anyone(*ent_spellings):
        spellings = [s for s in (str(f or "").strip() for f in ent_spellings)
                     if s]
        if not names or not spellings:
            return True
        return any(
            all(not _enclosure_conceals(sc, observer, form)
                for form in spellings)
            for observer in names
        )

    by_name = {}
    for eid, ent in entities.items():
        if isinstance(ent, dict):
            name = str(ent.get("name") or "").strip()
            if name:
                by_name.setdefault(name.casefold(), []).append(eid)

    projected = {}
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            projected[eid] = ent
            continue
        name = str(ent.get("name") or "").strip()
        # Keep the id when the name is missing or shared, so two entities
        # never collapse into one payload entry.
        key = name if name and len(by_name.get(name.casefold(), ())) == 1 \
            else eid
        drop = set(_ENTITY_LOOKUP_ONLY_FIELDS)
        if not _state_reaches_anyone(name, eid):
            drop.add("state")
        if eid in _inhabited_by_a_perceiver:
            # YOU CANNOT SEE THE OUTSIDE OF WHAT YOU ARE STANDING INSIDE.
            # `description` is an entity's EXTERIOR -- what a body in the room
            # around it takes in. Handed to its own occupant it reads as a
            # thing across the way. Live (chat 58, t38): the player stood in
            # the TARDIS console room and her view had "a blue police box --
            # its paint darkened by rain -- settles with a heavy thud on the
            # cobbles", which is the box she was standing in, landing, seen
            # from inside itself.
            #
            # The entity itself STAYS -- the room's own `parent_entity`
            # already tells the reader what they are inside, and presence is
            # not the leak. Only the outward appearance goes. (`state` is
            # separately withheld here by the containment gate above, which
            # predates this and is not changed by it.)
            drop.add("description")
        projected[key] = {k: v for k, v in ent.items() if k not in drop}
    return projected


def _char_known_tags(sheet):
    """(depth tiers, excluded titles, compartments) for one mind.

    Three returns rather than two because knowledge has three axes and the
    third one -- WHO may know a thing -- had no representation at all. See
    `mind.memory_lore_entries.knowledge_for_character`.
    """
    config = character_knowledge_config(sheet)
    tags = [tag for tag in ("common", "scholarly", "esoteric") if config.get(tag)]
    return tags, config.get("excluded_titles") or [], config.get("circles") or []

def _character_display_name(row):
    return character_name_from_text(row["sheet"])

def _normalize_scene_patch(value):
    patch = dict(value or {})
    for key in ("rooms", "entities", "positions", "stations"):
        if not isinstance(patch.get(key), dict):
            patch[key] = {}
    for key in ("remove_entities", "remove_rooms", "remove_adjacent"):
        if not isinstance(patch.get(key), list):
            patch[key] = []
    return patch

def _sequence_has_content(result):
    return any(
        (event.get("text") if event.get("type") == "speech"
         else (event.get("content") if event.get("type") == "communication"
               else event.get("attempt")))
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
            cast_names.add(character_name_from_text(row["sheet"]).casefold())
        except Exception:
            continue
    if addresses & cast_names:
        return False
    for event in _dict_list(result.get("sequence")):
        if event.get("type") == "communication":
            if str(event.get("act") or "").casefold() in (
                    "ask", "question", "request", "instruct"):
                targets = {str(value).casefold()
                           for value in event.get("targets") or []}
                if not targets or targets & aliases:
                    return True
            continue
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

def _element_effect_text(elem):
    """Every effect `kind` an action element declares, joined for text tests."""
    effects = list(_list(elem.get("intended_effects"))) + list(
        _list(elem.get("asserted_effects")))
    return " ".join(
        str(eff.get("kind") or "") for eff in effects if isinstance(eff, dict))


def authored_other_subject(elem, name_forms, actor_forms=()):
    """The cast id whose OWN cognition, volition, or involuntary response a
    player-authored action element declares -- or None when the element is the
    player's own act.

    `name_forms` maps cast id -> casefolded name/alias forms identifying that
    character; `actor_forms` are the declaring player's own forms.

    Two shapes are caught, both requiring another mind to be the SUBJECT of an
    interior or autonomous outcome:
      1. the element OPENS with a cast member's name ('Dr. Moon remembers she
         has her phone', 'Dr. Moon gives in');
      2. a noun/pronoun-led clause names exactly one cast member as the
         experiencer of such an outcome ('the strain finally pushes Dr. Moon
         over the edge') -- the same puppeting written indirectly, which the
         leading-subject rule alone misses.

    A verb-led attempt is the player's own predicate by the sequence
    convention, and an attempt the player leads by name is theirs, so neither
    is rerouted -- 'stabs Sarah' stays the player's act and Sarah's response
    is resolved through the reaction phase. A physical NPC beat with no
    interior or autonomous outcome ('Dr. Moon steps back') is likewise left
    for the world/perception path.

    The autonomy test is applied to the clause the named character is the
    SUBJECT of, never to the whole attempt -- dropping a player-declared act
    because a later clause happens to contain an ordinary word like 'enjoy'
    would violate the Director's own floor against silently replacing the
    player's declared action (AGENTS.md)."""
    if not isinstance(elem, dict) or elem.get("type") != "action":
        return None
    att = str(elem.get("attempt") or "").strip()
    low = att.casefold()
    if not low:
        return None

    def _predicate_is_autonomous(predicate):
        return (_is_mental_action(None, predicate)
                or _is_autonomous_response(None, predicate))

    # Shape 1: the attempt OPENS with a cast member's name, so the declared
    # verb and the clause that follows are both that character's predicate.
    for cid, forms in (name_forms or {}).items():
        for form in forms:
            if not any(low.startswith(form + suf) for suf in (" ", "'", "’")):
                continue
            if (_is_mental_action(elem.get("verb"), "")
                    or _is_autonomous_response(
                        elem.get("verb"), _element_effect_text(elem))
                    or _predicate_is_autonomous(
                        _predicate_after_name(low, len(form)))):
                return cid
            return None

    # Shape 2: a noun/pronoun-led clause names exactly one cast member as the
    # experiencer. The declared verb belongs to the leading noun here, not to
    # the character, so ONLY the clause following their name can qualify --
    # otherwise 'I remember Dr. Moon's face' (verb: remember) would reroute the
    # player's own recall into an offer for Dr. Moon.
    lead_tokens = re.split(r"[^\w']+", low, maxsplit=1)
    lead = lead_tokens[0] if lead_tokens else ""
    if lead in {str(f).casefold() for f in (actor_forms or ())}:
        return None
    # Words that can OPEN a clause without being its verb. A player action element
    # is authored verb-first by convention ('takes a deep breath...'), so an
    # attempt opening with one of these is a noun/pronoun-led clause -- somebody
    # or something OTHER than the declaring player is its subject.
    if lead not in _ling("_SUBJECT_LEADS"):
        return None
    named = []
    for cid, forms in (name_forms or {}).items():
        for form in forms:
            hit = re.search(rf"\b{re.escape(form)}\b", low)
            if hit:
                named.append((cid, hit.end()))
                break
    if len(named) != 1:
        return None
    cid, name_end = named[0]
    return cid if _predicate_is_autonomous(
        _predicate_after_name(low, name_end)) else None


def bind_sequence_targets(sequence, target_forms):
    """Fill an action/communication element's EMPTY ``targets`` from names.

    The director routinely emits an act that plainly lands on a character with
    `targets: []` -- and every downstream seam that asks "does this land on
    another body?" (the reaction-phase gate, claim subject binding, perception's
    targeted-observer check) reads `targets`, so an unbound act is invisible to
    all of them. Binding is by NAME because `ActionElement.targets` is typed as
    display names and perception matches them casefolded. Only ever ADDS a
    binding the text already supports; an element the director bound itself is
    left untouched.

    Deliberately does NOT mirror the name onto effects that left `target_id`
    null. A mention is evidence the act CONCERNS that character, which is all
    `targets` claims; an effect's `target_id` is the stronger claim that the
    outcome LANDS on them, and inferring it from the same mention manufactured
    authority claims the director never authored ('dodge away from Sarah' does
    not put an effect on Sarah). `_extract_authority_claims` reads the same
    name evidence through its own `target_forms` guard instead."""
    bound = 0
    for elem in _dict_list(sequence):
        if elem.get("type") not in ("action", "communication") \
                or elem.get("targets"):
            continue
        haystack = (f"{elem.get('attempt') or ''} "
                    f"{elem.get('content') or ''} "
                    f"{_element_effect_text(elem)}").casefold()
        if not haystack.strip():
            continue
        names = []
        for display, forms in (target_forms or {}).items():
            if any(re.search(rf"\b{re.escape(form)}\b", haystack)
                   for form in forms):
                names.append(display)
        if not names:
            continue
        elem["targets"] = names
        bound += 1
    return bound


def _requires_reaction_phase(event, valid_actor_ids, actor_names):
    """True when a contestable act lands on another character and asserts an
    outcome on them -- the case the reaction phase exists to adjudicate.

    The gate used to demand a verb from a small combat whitelist, so only
    violence could earn a reaction: any other contestable outcome asserted on a
    character's body (a grip they might break, an intimate act, a persuasion
    landing) was resolved with no chance for that character to contest it
    physically. Contestability plus a bound target plus a declared effect is
    the real condition; the whitelist and the multi-stage cues now only widen
    it, catching acts that declare no effect of their own."""
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
        event.get("intended_effects")
        or event.get("asserted_effects")
        or verb in _ling("_REACTIVE_VERBS")
        or any(term in attempt for term in _ling("_REACTIVE_VERBS"))
        or stage in _REACTIVE_STAGES
    )

def _requires_director_resolution(result):
    """Does this declaration need the Director before anyone can answer it.

    It ends the BEAT in `interaction_loop`, so the bar is "nobody can
    sensibly respond until the world says what happened" -- not "this act
    involves another person".

    HAVING A TARGET IS NOT THAT BAR, and treating it as one is what made
    conversation impossible. In a conversation every piece of ordinary body
    language is aimed at whoever you are talking to: a nod, a glance, an ear
    turning. Live, chat 38 t144-t147 -- the player deliberately stayed silent
    for four turns to let two characters talk -- and all four ended after a
    single exchange on acts like "offering a small nod of acknowledgment to
    Tamamo", "shifts gaze fully to the Doctor" and "remains motionless with
    steady gaze on Tamamo". Nobody can contest a nod. Corpus-wide, 1002 of
    1439 character-declared actions were asserted, immediate, and targeted --
    70% of every act a character takes was ending the beat.

    `commitment` is the Director's OWN answer to this question and it
    discriminates cleanly: `contestable` reads "Tightens grip on the caught
    prey's shoulder, wrenching upward", "Closes the 1.5-meter gap in two quick
    steps"; `asserted` reads "nods once slowly". Only 82 of those 1439 are
    contestable. The conflict-verb list stays as a backstop under a
    mislabelled commitment, and covers movement (`leave`/`enter`), which needs
    resolution however confidently it is declared.
    """
    actions = [
        e for e in _dict_list(result.get("sequence"))
        if e.get("type") == "action"
    ]
    for action in actions:
        text = str(action.get("attempt") or "").casefold()
        if action.get("visibility") == "concealed":
            return True
        if action.get("commitment") == "contestable":
            return True
        if any(term in text for term in _ling("_CONFLICT_VERBS")):
            return True
    return False

def _classify_action_commitment(raw_text):
    """Classify an action as asserted or contestable."""
    text = (raw_text or "").casefold().strip()
    if not text:
        return "contestable"
    if any(cue in text for cue in _ling("ATTEMPT_CUES")):
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

def _named_cast_subject(text, target_forms):
    """The single cast display name `text` names, or None when it names none
    or more than one (an ambiguous subject is worse than an absent one)."""
    low = str(text or "").casefold()
    if not low.strip():
        return None
    hits = [
        display for display, forms in (target_forms or {}).items()
        if any(re.search(rf"\b{re.escape(form)}\b", low) for form in forms)
    ]
    return hits[0] if len(hits) == 1 else None


def _effect_subject(event, eff, actor_name, target_forms, actor_forms):
    """Who ONE effect is about, and whether that answer is a guess.

    `targets` is a property of the ELEMENT; the effects hanging off it are
    separate claims, and the question "who is this about" is asked once per
    claim. Scoping the self-fallback to the element meant an element that acts
    on somebody AND asserts something about the actor's own body lost the
    subject on the body claim -- and `_named_cast_subject`, the guard added to
    catch a claim plainly about someone else, was nested INSIDE the same
    condition and so could not run there either.

    Measured over every stored `director_interpret` active variant in the live
    database, read-only: 1,673 effect claims, 856 (51.2%) with no subject, and
    703 of those 856 hang off an element that DID name targets -- which is
    exactly this scope error. Every one of them lands in
    `director_reconcile._player_claim_findings`' "no resolvable subject;
    coverage not checkable" note, so the player's asserted effect is never held
    against the diff at all.
    """
    if eff.get("target_id"):
        return eff["target_id"], False
    own_text = " ".join(str(part) for part in
                        (eff.get("kind"), eff.get("details")) if part)
    named = _named_cast_subject(own_text, target_forms)
    if named:
        return named, True
    # The effect's own text naming the ACTOR is the case the element scope hid:
    # "Hinami is seated on the bed" on an element whose targets name someone
    # else. It is the player's own body, and it is checkable.
    if actor_name and any(
            re.search(cue_boundary_pattern(re.escape(form)), own_text, re.I)
            for form in (actor_forms or ()) if form):
        return actor_name, True
    if event.get("targets"):
        # The element named somebody and this effect named nobody: a dropped
        # reference, not the self. Left for the Director to adjudicate, as
        # before -- resolving it to the player would hand them authorship of
        # another character's body.
        return None, False
    named = _named_cast_subject(
        f"{event.get('attempt') or ''} {_element_effect_text(event)}",
        target_forms)
    return (named or actor_name), bool(named or actor_name)


def _extract_authority_claims(sequence, raw_input, actor_name=None,
                              target_forms=None):
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
    of world facts.

    target_forms (cast display name -> casefolded match forms) closes the
    hole that fallback opened: when the model leaves BOTH targets and
    target_id empty on an act whose text is plainly about another character,
    "no targets" is not evidence of self-direction, and stamping the player
    as subject hands them authorship of that character's body. Naming the
    cast member the text does is strictly better than either wrong answer --
    the resolve seam can then actually check the claim's coverage."""
    fallback_text = str(raw_input or "")
    actor_forms = _player_name_forms(actor_name) if actor_name else ()
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
        if commitment == "asserted":
            for effect_index, effect in enumerate(
                event.get("asserted_effects") or []
            ):
                eff = _normalize_effect(effect)
                if eff is None:
                    continue
                predicate = str(eff.get("kind") or "").strip()
                if not predicate and not eff.get("details"):
                    # Nothing was claimed. An empty predicate with a resolvable
                    # subject becomes an omission reading "player-asserted
                    # completed effect '' on <subject>", which buys a full
                    # resolve_repair Director call for a claim with no content.
                    # Measured live: 48 of 1,673 effect claims (2.9%), and all
                    # 48 carry an empty `value` too, so nothing is lost.
                    continue
                subject_id, inferred = _effect_subject(
                    event, eff, actor_name, target_forms, actor_forms)
                claims.append({
                    "claim_id": f"claim:{i}:effect:{effect_index}",
                    "scope": "effect",
                    "subject_id": subject_id,
                    # Whether that subject is the model's answer or this
                    # function's GUESS -- "named no target" is not the same
                    # fact as "was about my own body". See
                    # `_claim_authority_kind`, which may not read a guess as a
                    # grant.
                    "subject_inferred": inferred,
                    "predicate": predicate,
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
                predicate = str(eff.get("kind") or "").strip()
                if not predicate and not eff.get("details"):
                    continue
                subject_id, inferred = _effect_subject(
                    event, eff, actor_name, target_forms, actor_forms)
                claims.append({
                    "claim_id": f"claim:{i}:intent:{effect_index}",
                    "scope": "intent",
                    "subject_id": subject_id,
                    "subject_inferred": inferred,
                    "predicate": predicate,
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
    max_tokens=None,   # the configured ceiling; see complete_validated_json
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
    # The FIRST complete object, before the greedy span below. A model that
    # answers and then keeps talking has still answered: observed live, a
    # narrator emitted valid JSON, then "That is my final answer... I am done.
    # Now I will output the JSON as the final message.", then the whole object
    # again, and again. `\{.*\}` is greedy, so it spanned from the first brace
    # to the LAST one across every repetition -- not valid JSON -- and this
    # function fell through to `{fallback_key: <the entire mess>}`, discarding
    # a complete and correct answer the model had already given.
    #
    # `llm_quality.strict_json_parse` has carried a string-aware brace scanner
    # for exactly this since before the loose path existed; reusing it rather
    # than writing a second one keeps the two from disagreeing about what
    # counts as the answer.
    try:
        from llm.llm_quality import strict_json_parse

        first = strict_json_parse(t)
        if isinstance(first, dict):
            return first
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

def _room_notes_for_view(rdata, room_id, ctx, scene=None):
    """The room's description as a MIND receives it.

    One spelling of `(the scene's own notes) or (the lore layer's)`, which six
    perceiver payloads in `agents/perception` had written out by hand -- so a
    rule taught to one of them was taught to none of the others. The rule is
    that engine bookkeeping is not world text: both sources can carry a note
    the engine wrote about its own retrieval, and neither may deliver it. See
    `story/provenance_text`.
    """
    notes = (rdata or {}).get("notes") if isinstance(rdata, dict) else None
    if notes:
        return strip_engine_provenance(notes)
    return _room_notes_from_lore(room_id, ctx, scene)


def _room_notes_from_lore(room_id, ctx, scene=None):
    """The room's description as PROSE, for delivery to a mind.

    Every return runs through `strip_engine_provenance`: a `layout` entry the
    engine wrote for a room it had no canon for may carry the reason it was
    written, and that reason is bookkeeping about a retrieval, not a fact about
    the room. It stays on the lore row's `source_notes` where an author and an
    audit can read it; it does not travel into a view. See
    `story/provenance_text` for the measurement.
    """
    if not room_id:
        return ""
    sc = scene if scene is not None else get_scene(ctx.chat.id, ctx.chat)
    rdata = (sc.get("rooms") or {}).get(room_id)
    if rdata and rdata.get("notes"):
        return strip_engine_provenance(rdata["notes"])
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
            return strip_engine_provenance(content)[:600]
    for entry in lore_for(ctx):
        _k = entry.get("keys")
        keys = (" ".join(map(str, _k)) if isinstance(_k, list) else str(_k or "")).lower()
        content = entry.get("content") or ""
        if (room_norm in keys or room_id.lower() in keys) and content:
            if blocked and _keys_reference_blocked(keys, blocked):
                continue
            return strip_engine_provenance(content)[:600]
    return ""

# A stage direction written INSIDE a speech element: "*leans in* Sit down."
# Bounded and single-line on purpose: an unpaired asterisk in ordinary prose
# must not swallow the rest of the line looking for its partner.
_STAGE_DIRECTION_RE = re.compile(r"\*([^*\n]{1,400}?)\*")


def split_stage_directions(text):
    """Speech text -> (the words actually spoken, the conduct written into it).

    A character model trained on chat roleplay writes conduct inside the line
    it speaks -- "*leans in and sets a hand flat on her shoulder* You will want
    to sit down" -- instead of emitting the {type:'action'} element the
    sequence contract already provides beside it. Nothing forces this; one live
    beat declared a proper action element AND smuggled a second act into the
    speech in the same breath.

    The engine had no opinion about the contents of `text`, so everything in it
    was treated as SOUND. A body movement then went through the whole
    audibility apparatus -- distance, muffling, enclosure, deafness -- and a
    listener who could hear but not see was told about it in so many words:
    `You hear Reya say: "*leans in...*"`. That is a channel violation. Not a
    knowledge one -- the person being touched would feel it -- but the flow is
    wrong, and a wrong flow is an engine failure, never a model's, so the floor
    here is deterministic rather than a request in the prompt.

    Measured before the fix (chat 62, 12 turns): 52% of that chat's speech
    elements carried one, against 0.9% across the rest of the corpus. It grew
    turn over turn because the span was stored in the speaker's own episodic
    memory as words she SAID and read back to her on the next beat, and it was
    also the cause of a second symptom -- the Director, a different model,
    re-rendered the stage direction as prose, which no longer matched the
    declaration, so the verbatim-speech guard dropped the line as invented on
    7 of 12 turns against 7 of 1,715 turns corpus-wide.

    A ONE-WORD span is markdown emphasis, not a stage direction ("what does it
    *feel* like") -- the asterisks come off and the word stays spoken.

    `tone` was considered as the home for the vocal-manner spans (a laugh, a
    drop in register) and rejected. `_inject_dialogue` renders tone only when
    the listener can SEE the speaker, so an audible laugh parked there is lost
    in the dark -- exactly the same class of bug one layer down. Every span
    becomes conduct instead, and perception delivers it by whatever channel the
    act actually engages, which is perception's job and not this function's.
    """
    raw = str(text or "")
    if "*" not in raw:
        return raw, []
    spans = []

    def _take(match):
        body = " ".join(match.group(1).split())
        if not body:
            return ""
        if len(body.split()) == 1:
            # Emphasis on a single spoken word. It stays in the line.
            return body
        spans.append(body)
        return ""

    spoken = _STAGE_DIRECTION_RE.sub(_take, raw)
    # Collapse the whitespace and orphaned punctuation the excision leaves
    # behind, so "*leans in* You will..." does not become " You will...".
    spoken = re.sub(r"\s{2,}", " ", spoken).strip()
    spoken = re.sub(r"^[,;:.\-—\s]+", "", spoken).strip()
    return spoken, spans


def _promoted_stage_action(span, speech_elem):
    """One excised stage direction, as the action element it should have been.

    It inherits the speech element's concealment: a stage direction inside a
    whispered aside was hidden by the words around it, and must not become
    overt conduct just because it moved onto its own channel. `observable` goes
    through the same mental-verb check `norm_sequence` applies to any other
    action, so "*thinks better of it*" resolves to an imperceptible beat rather
    than a visible one.
    """
    observable = "" if _is_mental_action("", span) else span
    return {
        "type": "action",
        "attempt": span,
        "observable": observable,
        "visibility": ("concealed"
                       if speech_elem.get("visibility") == "concealed"
                       else "overt"),
        "conceal_from": list(speech_elem.get("conceal_from") or []),
        "targets": [],
        "commitment": _classify_action_commitment(span),
        "verb": "",
        "stage": "immediate",
        "intended_effects": [],
        "asserted_effects": [],
        "_promoted": True,
    }


def collapse_duplicate_events(sequence, warn=None, asserted=None):
    """One declared act is one event.

    `speech`, `action` and `actions` are MIRRORS of `sequence`, not additional
    channels -- and `norm_sequence` treated them as additional, appending every
    entry of the scalar mirrors on top of a sequence that already held them.
    Measured on the real validated path:
    `{"sequence": [speech, "squirm", speech], "actions": [{"attempt": "squirm"}]}`
    came out as FOUR elements, and `assign_event_ids` labelled the one squirm
    `turn:1:player:1:action` AND `turn:1:player:3:action`. Nothing downstream
    collapsed them, so one declared act was adjudicated, perceived and narrated
    twice.

    IDENTITY IS THE DECLARATION, not the slot it arrived in: type, normalized
    content, targets, `stage` and `phase`. `stage`/`phase` are IN the key on
    purpose -- a declaration decomposed into approach-then-contact repeats its
    own text and is genuinely two events.

    The base tier is EXACT, and that is the whole safety argument. Dropping
    declared conduct is the failure this seam exists to prevent, so a
    restatement has to be a restatement: same words, same target, same phase.
    "grab the rifle" and "grab the rifle and rack it" overlap completely
    against the shorter and are two different declarations.

    `asserted` opens the narrower second tier for a REPAIR merge: elements at
    or after that index are additions, licensed only to cover a clause the
    coverage check found uncovered, and an addition that restates an already
    asserted action is by construction not that. Only there is content-word
    overlap used, on the same measure `_dedupe_promoted_actions` applies.

    A dropped element's dependents are rewritten onto its survivor, or
    `settle_sequence_dispositions` would block them as a missing prerequisite.
    """
    rows = [e for e in (sequence or []) if isinstance(e, dict)]
    if len(rows) < 2:
        return list(sequence or [])

    def _norm(text):
        return " ".join(str(text or "").casefold().split())

    def _content(element):
        kind = str(element.get("type") or "action")
        if kind == "speech":
            return _norm(element.get("text"))
        if kind == "communication":
            return _norm("%s %s" % (element.get("act") or "",
                                    element.get("content") or ""))
        if kind == "event":
            return _norm(element.get("description"))
        return _norm(element.get("observable") or element.get("attempt"))

    def _key(element):
        targets = sorted(str(t or "").strip().casefold()
                         for t in (element.get("targets") or []))
        return (str(element.get("type") or "action"), _content(element),
                tuple(targets), str(element.get("stage") or ""),
                str(element.get("phase") or ""))

    def _words(text):
        words = re.sub(r"[^\w\s]", " ", str(text or "")).lower().split()
        return {w for w in words if w not in _ling("_OVERLAP_STOPWORDS")}

    seen, kept, redirect = {}, [], {}
    for index, element in enumerate(rows):
        key = _key(element)
        survivor = seen.get(key)
        if survivor is None and asserted is not None and index >= asserted \
                and str(element.get("type") or "action") == "action":
            mine = _words(element.get("observable") or element.get("attempt"))
            if len(mine) >= 3:
                for earlier in kept:
                    if str(earlier.get("type") or "action") != "action":
                        continue
                    theirs = _words(earlier.get("observable")
                                    or earlier.get("attempt"))
                    if len(theirs) >= 3 and (
                            len(mine & theirs) / min(len(mine), len(theirs))
                            >= 0.8):
                        survivor = earlier
                        break
        if survivor is None:
            seen[key] = element
            kept.append(element)
            continue
        for field in ("event_id", "phase_id"):
            dropped_id = str(element.get(field) or "")
            if dropped_id:
                redirect[dropped_id] = str(survivor.get(field) or "")
        if warn is not None:
            warn("dropped a restatement of an already declared act: %r"
                 % (_content(element)[:80],))
    if redirect:
        for element in kept:
            deps = element.get("depends_on")
            if isinstance(deps, list):
                element["depends_on"] = [
                    redirect.get(str(d), d) for d in deps
                    if redirect.get(str(d), d)]
    return kept


def _dedupe_promoted_actions(clean):
    """Drop a promoted action the character ALSO declared properly.

    The live failure mode narrated one act twice in a single paragraph: once
    through a real action element and once through the copy smuggled into the
    speech. The two spellings are almost never identical -- "sets a hand on her
    shoulder" against "sets a hand FLAT on her shoulder" -- so the comparison is
    content-word overlap rather than containment, measured against the SHORTER
    of the two so a long elaboration still matches the short declaration it
    elaborates.

    Deliberately not fuzzier than that. A false match silently drops conduct
    the character declared, which is the failure this whole path exists to
    prevent; a false miss only costs a duplicated beat the narrator can merge.
    """
    def _content(text):
        words = re.sub(r"[^\w\s]", " ", str(text or "")).lower().split()
        # Function words carry no evidence that two descriptions name the same act --
        # "on her" appears in every second stage direction -- so they are excluded
        # before the overlap in _dedupe_promoted_actions is measured.
        return {w for w in words if w not in _ling("_OVERLAP_STOPWORDS")}

    declared = [_content(e.get("observable") or e.get("attempt"))
                for e in clean
                if e.get("type") == "action" and not e.get("_promoted")]
    declared = [d for d in declared if len(d) >= 3]
    kept = []
    for e in clean:
        if e.get("type") == "action" and e.get("_promoted"):
            mine = _content(e.get("attempt"))
            if len(mine) >= 3 and any(
                    len(mine & d) / min(len(mine), len(d)) >= 0.8
                    for d in declared):
                continue
        kept.append(e)
    return kept


# Below this, a line has nothing to cut. "Wait." interrupted is still "Wait."
# -- truncating it produces "Wait.—", which reads as a typo, and fictionally
# there is no room to get inside a one-word line anyway.
_MIN_INTERRUPTIBLE_WORDS = 5


def cut_short_speech(text, ratio=0.6):
    """A spoken line as it lands when somebody cuts in, or None to leave it.

    Returning None rather than a shortened string is the important half: a
    short line, or one the speaker already trailed off, is delivered WHOLE and
    the interrupting beat simply follows it. Forcing a cut on everything is
    what makes an interruption mechanic read as a bug.

    Where the cut falls was chosen by reading the output rather than by
    picking a number. A flat halfway cut lands mid-phrase ("the shipment
    left—"); stopping at a breath point lands where a person actually gets cut
    off ("the shipment left on Tuesday—"). So: keep whole sentences, cut the
    final one near `ratio`, and slide that cut to the nearest comma or
    conjunction within a couple of words.

    The em dash replaces whatever punctuation it lands on, because "to do,—"
    and "hearth.—" are both wrong and the dash is doing that job now.
    """
    body = " ".join(str(text or "").split())
    if not body:
        return None
    # Already trailed off -- the writer has done this themselves.
    if body.endswith(("—", "–", "-", "...", "…")):
        return None
    if len(body.split()) < _MIN_INTERRUPTIBLE_WORDS:
        return None

    sentences = re.split(r"(?<=[.!?])\s+", body)
    head, tail = sentences[:-1], sentences[-1]
    words = tail.split()
    if len(words) < 3 and head:
        kept = words
    else:
        target = max(1, int(len(words) * ratio))
        keep = target
        for index in range(max(1, target - 2), min(len(words), target + 3)):
            if words[index - 1].endswith(","):
                keep = index
                break
            # Words a sentence leans on rather than lands on. An interruption arrives where
            # the speaker drew breath, and the breath is taken just before one of these or
            # just after a comma -- not at an arbitrary word count.
            if words[index].lower().strip(",;:") in _ling("_BREATH_CONJUNCTIONS"):
                keep = index
                break
            if words[index - 1].lower().strip(",;:") in _ling("_BREATH_CONJUNCTIONS"):
                keep = max(1, index - 1)
                break
        kept = words[:keep]
    joined = " ".join(head + [" ".join(kept)]) if head else " ".join(kept)
    return re.sub(r"[.,;:!?\s—–-]+$", "", joined) + "—"


def norm_sequence(out, warn=None):
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
                # Conduct written into the spoken line comes out FIRST and
                # becomes its own action, placed immediately before the speech
                # it was buried in. See split_stage_directions: leaving it in
                # `text` routes a body movement down the acoustic channel.
                txt, _stage_spans = split_stage_directions(str(txt))
                for _span in _stage_spans:
                    clean.append(_promoted_stage_action(_span, e))
                    if warn:
                        warn("moved a stage direction out of spoken text into "
                             "its own action: '%s'" % _span[:80])
                        if not clean[-1]["observable"]:
                            warn("classified as interior, so no perceiver "
                                 "receives it: %r" % _span[:120])
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
                    # Who this lands on top of, if the character declared it as
                    # cutting somebody off. Resolved deterministically in the
                    # interaction loop against who has actually spoken this
                    # beat -- a name here is a claim, not an outcome.
                    "interrupts": str(e.get("interrupts") or "").strip(),
                    "visibility": "concealed" if e.get("visibility") == "concealed" else "overt",
                    "conceal_from": e.get("conceal_from") or [],
                    "targets": e.get("targets") or [],
                    "phase_id": str(e.get("phase_id") or ""),
                    "phase": str(e.get("phase") or "atomic"),
                    "depends_on": [str(x) for x in e.get("depends_on") or []
                                   if str(x).strip()],
                    "participants": [str(x) for x in
                                     e.get("participants") or []
                                     if str(x).strip()],
                    # raw (pre-normalization) signals, consumed by the
                    # concealment backstop below and stripped before return.
                    "_raw_vis": e.get("visibility"),
                    "_raw_vol": e.get("volume"),
                })
        elif t in _COMMUNICATIVE_TYPES:
            content = e.get("content") or e.get("topic") or e.get("meaning")
            if content:
                targets = e.get("targets") or e.get("target") or []
                if not isinstance(targets, list):
                    targets = [targets]
                clean.append({
                    "type": "communication",
                    "act": str(e.get("act") or e.get("kind") or "say"),
                    "content": " ".join(str(content).split()),
                    "targets": targets,
                    "volume": normalize_speech_volume(e.get("volume")),
                    "tone": str(e.get("tone") or ""),
                    "visibility": ("concealed" if
                                   e.get("visibility") == "concealed"
                                   else "overt"),
                    "conceal_from": e.get("conceal_from") or [],
                    "phase_id": str(e.get("phase_id") or ""),
                    "phase": str(e.get("phase") or "atomic"),
                    "depends_on": [str(x) for x in e.get("depends_on") or []
                                   if str(x).strip()],
                    "participants": [str(x) for x in
                                     e.get("participants") or []
                                     if str(x).strip()],
                })
        elif t == "ponder":
            # Private cognitive action. It never enters the public sequence,
            # Director resolution, perception, or narration. Commit stores one
            # bounded query for the next character turn.
            query = " ".join(str(e.get("query") or "").split())[:240]
            why = " ".join(str(e.get("why") or "").split())[:240]
            if query and why:
                out["ponder"] = {
                    "type": "ponder", "query": query, "why": why}
            elif (query or why) and warn:
                # A ponder is by design not in the public sequence, so nothing
                # downstream can notice it went missing -- there is no view, no
                # percept and no prose it would have shown up in. Dropping half
                # of one silently is the same failure shape as blanking an act.
                warn("dropped a ponder missing its %s: %r"
                     % ("why" if query else "query", (query or why)[:80]))
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
                    "phase_id": str(e.get("phase_id") or ""),
                    "phase": str(e.get("phase") or "atomic"),
                    "depends_on": [str(x) for x in e.get("depends_on") or []
                                   if str(x).strip()],
                    "participants": [str(x) for x in
                                     e.get("participants") or []
                                     if str(x).strip()],
                    "requires_contacts": [dict(x) for x in
                                          e.get("requires_contacts") or []
                                          if isinstance(x, dict)],
                    "referents": [dict(x) for x in e.get("referents") or []
                                  if isinstance(x, dict)],
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
                    if _is_mental_action(e.get("verb"), att):
                        observable = ""
                        # SAY SO. Blanking is a decision that nobody will ever
                        # perceive this act -- it is skipped by every delivery
                        # site, so there is no view, no percept and no memory
                        # to notice it by, and the only trace left behind is an
                        # empty string in a stored variant.
                        if warn:
                            warn("classified as interior, so no perceiver "
                                 "receives it: %r" % att[:120])
                    else:
                        observable = att
                clean.append({
                    "type": "action",
                    "attempt": att,
                    "observable": str(observable),
                    # A blow, a hand over a mouth, a grab -- conduct cuts a line
                    # off exactly as a louder voice does.
                    "interrupts": str(e.get("interrupts") or "").strip(),
                    "visibility": e.get("visibility", "overt"),
                    "conceal_from": e.get("conceal_from") or [],
                    "targets": tg,
                    "commitment": commitment,
                    "verb": e.get("verb", ""),
                    "stage": e.get("stage", "immediate"),
                    "intended_effects": intended_effects,
                    "asserted_effects": asserted_effects,
                    "phase_id": str(e.get("phase_id") or ""),
                    "phase": str(e.get("phase") or "atomic"),
                    "depends_on": [str(x) for x in e.get("depends_on") or []
                                   if str(x).strip()],
                    "participants": [str(x) for x in
                                     e.get("participants") or []
                                     if str(x).strip()],
                    "requires_contacts": [dict(x) for x in
                                          e.get("requires_contacts") or []
                                          if isinstance(x, dict)],
                    "referents": [dict(x) for x in e.get("referents") or []
                                  if isinstance(x, dict)],
                })
    # A promoted stage direction the character also declared as a real action
    # is the same act twice, and the narrator rendered both.
    clean = _dedupe_promoted_actions(clean)
    clean = collapse_duplicate_events(clean, warn=warn)
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
    #
    # THAT LAST PARENTHESIS HOLDS ONLY ON THIS PATH, and the case it does not
    # cover was live for four stored beats. Here the addressee is recovered
    # from the concealing ACTION's `targets`, which is why over-concealing is
    # safe; but when the model writes the addressee into the SPEECH's own
    # explicit `conceal_from`, the skip on the next line preserves it verbatim
    # and nothing subtracts anything -- the addressee is made deaf by the
    # field that was supposed to protect them. It cannot be fixed here:
    # `targets` carries a NAME and `conceal_from` carries a cast ID, and this
    # function never sees `flow.addressed_to`, the one place both encodings of
    # the audience exist. `schemas._uncross_concealed_speech` does it there.
    concealed_from_union, conceal_targets = [], []
    for e in clean:
        if e["type"] in ("action", "communication") \
                and e.get("visibility") == "concealed":
            for cf in e.get("conceal_from") or []:
                if cf not in concealed_from_union:
                    concealed_from_union.append(cf)
            for tg in e.get("targets") or []:
                if tg not in conceal_targets:
                    conceal_targets.append(tg)
    propagate = [cf for cf in concealed_from_union if cf not in conceal_targets]
    if propagate:
        for e in clean:
            if e["type"] not in ("speech", "communication") \
                    or e.get("visibility") == "concealed":
                continue
            explicitly_public = (e.get("_raw_vis") == "overt") or (e.get("_raw_vol") in ("loud", "shout"))
            if explicitly_public:
                continue
            e["visibility"] = "concealed"
            e["conceal_from"] = list(propagate)
    for e in clean:
        e.pop("_raw_vis", None)
        e.pop("_raw_vol", None)
        e.pop("_promoted", None)

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


#: What two spoken elements must agree on before they can be ONE delivery.
#: Every field here answers a question about DELIVERY -- who may hear it, how
#: loudly, at whom it is aimed, and which phase of a staged act it belongs to
#: -- so two elements that disagree on any of them are two deliveries however
#: adjacent they sit, and stay two. Tone is deliberately absent: a voice
#: shifts register inside one turn at talk, and a change of register is not a
#: change of delivery.
_DELIVERY_KEYS = ("volume", "visibility", "conceal_from", "targets",
                  "phase", "phase_id", "depends_on", "participants")


def _delivery_signature(element):
    return tuple(
        tuple(element.get(key) or ()) if key in (
            "conceal_from", "targets", "depends_on", "participants")
        else str(element.get(key) or "")
        for key in _DELIVERY_KEYS
    )


def fuse_speech_run(out, warn=None):
    """CONSECUTIVE LINES ONE MOUTH SPEAKS WITH NOTHING BETWEEN THEM ARE ONE
    UTTERANCE.

    The speech budget's own contract already says this. It defines a line as
    "one separate beat of talk, delivered between other conduct" and states
    outright that "multiple lines are not one speech split by punctuation:
    they are separate utterances". A run of `{type: "speech"}` elements with
    no conduct between them is exactly the thing that contract forbids -- one
    turn at talk, split at its full stops -- and nothing enforced it, so the
    engine carried the split all the way to the page.

    IT IS THE PAGE THAT PAYS. Each element becomes its own `dialogue_log`
    entry, its own `speech_percept`, its own "X says in a Y voice: ..."
    sentence in every view, and the narrator sets what the view hands it: N
    quoted lines from one mouth, back to back, with no narration or
    attribution between them. Measured over the 38 stored beats of chat 98:
    26 of the 51 rounds that spoke at all emitted two or three speech
    elements, and one beat (turn 29) put SIX quoted lines from one mouth on
    the page in two rounds of three. The same split also repeats the
    attribution, which is where "his voice was measured / formal, precise /
    formal, declarative" inside one beat comes from.

    So the engine states the rule deterministically instead of asking. This
    SUBTRACTS: it merges deliveries, invents no words, drops none, and can
    only ever reduce the number of separate lines attributed to a mouth. Two
    elements fuse only when they agree on every DELIVERY attribute
    (`_DELIVERY_KEYS`) and the later one claims no interruption -- a whisper
    inside a spoken turn, an aside concealed from one party, or a line that
    cuts into somebody is a genuinely separate delivery and keeps its
    boundary. The fused element keeps the first's tone when the run agrees on
    one and drops it when the run does not, because no single adverbial is
    true of a delivery that changed register.

    A run separated by ANY other element -- an action, a mental beat, a
    communication -- is untouched: conduct between two lines is precisely what
    makes them two beats of talk, and that is the shape the budget is asking
    for.
    """
    sequence = out.get("sequence")
    if not isinstance(sequence, list) or len(sequence) < 2:
        return out
    fused, joined = [], 0
    for element in sequence:
        last = fused[-1] if fused else None
        if (isinstance(element, dict)
                and element.get("type") == "speech"
                and isinstance(last, dict)
                and last.get("type") == "speech"
                and not str(element.get("interrupts") or "").strip()
                and _delivery_signature(last) == _delivery_signature(element)):
            head = str(last.get("text") or "").strip()
            tail = str(element.get("text") or "").strip()
            if tail:
                last["text"] = (head + " " + tail).strip() if head else tail
                if str(last.get("tone") or "") != str(element.get("tone") or ""):
                    last["tone"] = ""
                joined += 1
            continue
        fused.append(dict(element) if isinstance(element, dict) else element)
    if joined and warn:
        warn(f"fused {joined} spoken line{'s' if joined > 1 else ''} into the "
             "utterance before it -- separate lines are separate beats of "
             "talk, delivered between other conduct")
    out["sequence"] = fused
    return _sync_sequence_mirrors(out) if joined else out


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

#: The word-runs of a NAME, in whatever script it is written. `[A-Za-z']+`
#: describes the Latin script rather than a name, and returns nothing at all
#: for the rest -- so every rule built on tokens (recognition variants,
#: standalone forms) simply stopped having anything to work with.
#:
#: A run in a script that does not space its words is one token; the joiners
#: those scripts put BETWEEN the parts of a name -- the katakana middle dot
#: and double hyphen -- are deliberately outside the classes, so 佐藤・ヒナミ
#: splits where a reader would split it. Latin runs are matched exactly as
#: before, hyphen and all, so no existing name tokenises differently.
_NAME_TOKEN_RE = re.compile(
    r"[A-Za-z']+"
    r"|[ぁ-ゖ]+|[ァ-ヺ]+|[㐀-䶿一-鿿豈-﫿]+|[가-힯]+|[฀-๿]+")

#: A short Latin token cannot be told from an ordinary word; a short token in
#: a script that does not space its words is a perfectly ordinary name --
#: 佐藤 is two characters and is a family name. The same distinction
#: `_scrub_unknown_identities` draws, for the same reason.
_NAME_TOKEN_MIN = 3
_UNSPACED_NAME_TOKEN_MIN = 2


def _name_tokens(text):
    """The word-runs of a name, in whatever script it is written."""
    return _NAME_TOKEN_RE.findall(str(text or ""))


def _name_token_floor(token):
    """The shortest this token could be and still identify somebody."""
    return (_UNSPACED_NAME_TOKEN_MIN if _UNSPACED_SCRIPT.match(token[:1])
            else _NAME_TOKEN_MIN)


def _display_floor(name, spaced=4):
    """The shortest a DISPLAY name can be and still be worth matching in prose.

    Four characters is a floor drawn for a spaced script, where a name that
    short is usually a common word too. An unspaced script writes the same
    amount of name in two or three characters -- 鉄の扉 is a full portal name
    at three -- so applying the spaced floor to it skips the guard outright,
    silently, on every portal and every room in the story.
    """
    return (_UNSPACED_NAME_TOKEN_MIN if _UNSPACED_SCRIPT.match(str(name)[:1])
            else spaced)


def _significant_name_tokens(name):
    """Lower-cased identifying tokens of a name -- titles, ranks and single
    initials removed. 'Commander Riker' -> {'riker'}."""
    out = set()
    for tok in _name_tokens(name):
        low = tok.strip(".'").casefold()
        if not low or len(low) < _name_token_floor(low):
            continue
        # Rank/title/honorific tokens dropped before comparing names, plus single-letter
        # middle initials. So "Commander Riker" and "Cmdr. Riker" reduce to {riker}.
        if low in _ling("_NAME_TITLE_TOKENS"):
            continue
        out.add(low)
    return out


def _recognizes(name, recognized):
    """Whether an observer who recognizes the `recognized` name forms also
    recognizes `name`, allowing a rank/title VARIANT of a known person
    (P7 / v3 V3: a background presence voiced as 'Commander Riker' was
    anonymized to 'the unfamiliar person' though the observer knew 'William T.
    Riker').

    Deliberately tight to protect the information barrier: a variant is
    recognized ONLY if every one of its significant tokens is contained in a
    single known name. That admits 'Commander Riker' against 'William T. Riker'
    but still anonymizes 'Commander Sato' (no shared token) AND 'Thomas Riker'
    (shares a surname but 'Thomas' is not known) -- a same-surname stranger
    stays a stranger.

    Lives here (not in agents/perception.py) so the narrator payload builders
    resolve speaker displays with the SAME recognition rule perception used to
    build the view -- role modules never import each other."""
    if name in recognized:
        return True
    tokens = _significant_name_tokens(name)
    if not tokens:
        return False
    for known_name in recognized:
        known_tokens = _significant_name_tokens(known_name)
        if known_tokens and tokens <= known_tokens:
            return True
    return False


def _identity_token_set(actor_name, aliases=None):
    """Casefolded word tokens of an actor's name and aliases -- the tokens
    that must never surface to an observer who does not recognize them."""
    tokens = set()
    for form in [actor_name] + list(aliases or []):
        for tok in re.split(r"[^\w]+", str(form or "")):
            if tok:
                tokens.add(tok.casefold())
    return tokens

def observer_label_fn(chat, observer_name, cast):
    """`name -> what THIS observer may call them`, for any payload that names
    a body outside perception's own scrubbing.

    Perception decides identity per observer and renders prose accordingly.
    Everything else that hands a character a NAME has to make the same
    decision, and until now nothing did -- so a structured field could hand
    over an identity the prose beside it was carefully withholding. Observed
    live: `perception.spatial_frame.ahead_entity` came from `scene.positions`,
    which is keyed by canonical name, and told a character who she was looking
    at. She had asked twice, in dialogue, and been refused both times; six
    beats later she used the surname aloud.

    Same rule as `agents/perception.py`'s own gate, from the same `known` map,
    through the same `_recognizes` predicate and the same
    `_unknown_actor_label`, so this is one identity floor rather than a second
    one that can drift from it. The predicate is the half that HAD drifted:
    membership in `known` is string equality, and perception asks `_recognizes`
    at nine sites, so a rank or title variant of somebody the observer knows
    ("Commander Riker" to a mind introduced to "William T. Riker") was a
    person in the view and a stranger in every payload beside it.
    """
    known = set((wget(chat["id"], "known", {}) or {}).get(observer_name) or [])
    sheets = {}
    for row in (cast or []):
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        name = character_name(sheet)
        if name:
            sheets[name] = sheet
    persona = persona_of(chat)
    p_name = persona_name(persona)
    if p_name:
        sheets.setdefault(p_name, persona)

    def label(name):
        text = str(name or "").strip()
        if not text or text == observer_name or _recognizes(text, known):
            return text
        sheet = sheets.get(text)
        if sheet is None:
            # Not a body this function knows about -- an entity id, a prop, a
            # room. Nothing to gate, and inventing a description for a lamp
            # would be worse than leaving it.
            return text
        return _unknown_actor_label(
            text, character_appearance(sheet), character_scene_keys(sheet)[1:])

    return label


def observer_name_scrub(chat, observer_name, cast):
    """`text -> the same text with unrecognized bodies renamed`, for a payload
    that hands a character PROSE somebody else wrote.

    `observer_label_fn` above gates a field that holds ONE name. This gates a
    field that holds a paragraph, and it exists because `world_knowledge` did
    not have either: lore entries are objective world record, they are written
    during play by the mapping stage, and that stage writes canonical names
    into their prose. Any character whose lore filter admitted the entry then
    read the name, met or not.

    Observed live (chat 38, t140): Tamamo had met the Doctor for the first
    time one beat earlier. Her `known` ledger was empty, her view called him
    "the lean energetic man", `ahead_entity` called him "the lean energetic
    man", her memories and her micro-perception all agreed -- and a lore entry
    in her payload opened "As The Doctor and Hinami walk deeper into the Deck
    14 corridor". She addressed him as "Doctor" in the same beat, and wrote
    "the lean energetic man now identified as Doctor" into her own concerns.
    Across the stored corpus, 65 lore entries in 22 chats name a cast member;
    16 of those were written during play.

    Whole-word only, and aliases too, because the entry that leaked used the
    plain registered name and a substring rule would maul any word containing
    it. Quoted spans are NOT exempt the way perception exempts them: a lore
    entry is not a transcript, and prose that quotes somebody naming a person
    is still telling the reader who they are.
    """
    label = observer_label_fn(chat, observer_name, cast)
    known = set((wget(chat["id"], "known", {}) or {}).get(observer_name) or [])
    sheets = []
    for row in (cast or []):
        try:
            sheets.append(json.loads(row["sheet"]))
        except Exception:
            continue
    # The player is a body in the room like any other, and lore written during
    # play names them more often than it names anyone else. Same source as
    # observer_label_fn's, so the two cannot disagree about who is gated.
    persona = persona_of(chat)
    if isinstance(persona, dict):
        sheets.append(persona)
    subjects = []
    for sheet in sheets:
        name = character_name(sheet)
        # `_recognizes`, not membership: the same predicate `observer_label_fn`
        # above resolves a label with, so a mind's structured payload and its
        # prose cannot disagree about who it has met.
        if not name or name == observer_name or _recognizes(name, known):
            continue
        forms = {name} | {
            str(alias) for alias in (character_scene_keys(sheet)[1:] or [])
            if str(alias or "").strip()
        }
        replacement = label(name)
        if replacement == name:
            continue
        for form in forms:
            subjects.append((form, replacement))
    # Longest first: "The Doctor" must win over a bare "Doctor" alias, or the
    # longer form is left half-rewritten.
    subjects.sort(key=lambda pair: -len(pair[0]))

    def scrub(text):
        if not isinstance(text, str) or not text or not subjects:
            return text
        for form, replacement in subjects:
            text = re.sub(rf"\b{re.escape(form)}\b", replacement, text)
        return text

    return scrub


def scrub_names_deep(value, scrub):
    """Apply a text scrub to every string in a nested payload value.

    Lore arrives as a list of dicts whose `content`, `title` and `keys` are all
    prose a mind will read; walking the structure keeps the caller from having
    to know which of them the current schema happens to use.
    """
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrub_names_deep(item, scrub) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_names_deep(item, scrub) for item in value)
    if isinstance(value, dict):
        return {key: scrub_names_deep(item, scrub) for key, item in value.items()}
    return value


#: Characters a generated label may never carry. A label is SPLICED INTO
#: PROSE that later passes parse structurally, and the identity scrub
#: (`_scrub_unknown_identities`) decides what it may rewrite by splitting on
#: `_QUOTED_SPAN_RE` and treating even segments as outside-quotes. So one
#: quote character inside a label does not merely look wrong -- it shifts
#: every span boundary after it and INVERTS the guard.
#:
#: Measured live, chat 82 t1: an appearance summary reading `Young
#: Korean-American woman, 5'7", with a lithe...` produced the label `the young
#: korean-american woman 5'7"`. Spliced into the speaker attribution, its
#: stray `"` made the attribution parse as quoted (protected) and the
#: character's actual spoken line parse as unquoted (scrubbed) -- so the
#: engine rewrote a name INSIDE delivered dialogue, which is the one thing
#: this whole area is built not to do. A speaker saying their own name is an
#: introduction, and an introduction is the channel by which a name is
#: legitimately learned; editing it does not close a leak, it destroys the
#: channel. The rendered quote broke too, and the fidelity tripwire fired on
#: the damage rather than the cause.
#: Double quotes only. A single quote BETWEEN word characters is a possessive
#: or a contraction -- "the young smith's apprentice" -- and cannot open a
#: span either, because `_QUOTED_SPAN_RE`'s single-quote alternative refuses an
#: opener preceded by a word character. Stripping those too turned every
#: possessive label into "the young smith s apprentice".
_LABEL_STRUCTURAL_CHARS = "\"\u201c\u201d"

#: A single quote that is NOT holding a word together, which is the only kind
#: that can act as a delimiter downstream.
_LABEL_LOOSE_QUOTE_RE = re.compile(r"(?<![^\W_])['\u2018\u2019]|['\u2018\u2019](?![^\W_])")


def _label_safe(text):
    """A label with the prose STRUCTURE stripped out of it -- see
    `_LABEL_STRUCTURAL_CHARS`. Whitespace is re-collapsed because removing a
    character can leave a double space where a word used to be."""
    cleaned = "".join(
        " " if ch in _LABEL_STRUCTURAL_CHARS else ch for ch in str(text or ""))
    cleaned = _LABEL_LOOSE_QUOTE_RE.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _unknown_actor_label(actor_name, appearance_text=None, aliases=None, *,
                         role=""):
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
    #
    # A ROLE WORN IN THE NAME IS NOT IDENTITY. A body's institution supplies
    # a public noun for what it is -- a rank, a duty, a trade -- and a minted
    # display name routinely carries it in front of the personal name
    # ("<rank> <given> <family>"). Set membership then treats that noun as an
    # identity token and subtracts it from the body's own appearance summary,
    # which for such a body IS the noun: everything is stripped, nothing
    # survives, and a person standing in a lit room reaches the view as the
    # generic fallback. Measured live, chat 98 turns 13-21: five crew, each
    # rendered "the unfamiliar person" while the crowd they had been
    # subtracted from called them ensigns aloud. The exemption is of the
    # role's own tokens and nothing else, so a summary that is the body's
    # PERSONAL name still strips to the fallback -- and it discloses nothing,
    # because the same noun is what `charter_crowd` already renders to any
    # observer for the band these bodies are members of. Nothing about "an
    # ensign" narrows down which ensign.
    if appearance_text:
        articles = frozenset(compositor_value("articles"))
        name_tokens = _identity_token_set(actor_name, aliases)
        if role:
            name_tokens -= _identity_token_set(role)
        cleaned = re.sub(
            r"^(?:" + "|".join(map(re.escape, articles)) + r")\s+", "",
            appearance_text.strip(), flags=re.I,
        ).replace(",", "")
        words = [w for w in cleaned.split()
                 if re.sub(r"[^\w]", "", w).casefold() not in name_tokens]
        # Dropping a leading name can expose the article that followed it
        # ("Hinami, a fox-eared..." -> "a fox-eared..."); re-strip it.
        while words and words[0].lower() in articles:
            words = words[1:]
        # A LINKING PARTICIPLE introduces a phrase, and the 5-word cap cuts
        # that phrase off part-way: appearance summaries overwhelmingly read
        # "<body> appearing in her early twenties" or "<body> wearing a
        # patched flight jacket", which cap to "...woman appearing" and
        # "...smuggler wearing a patched" -- both promising a clause neither
        # delivers. Truncating AT the participle rather than trimming it off
        # the end is what fixes the second case, where the participle is not
        # the last word. Only verbs that introduce a following phrase are
        # listed; a bare -ing rule would eat real nouns ("the figure in
        # mourning"). Applied before the cap so the kept words are the
        # distinguishing head of the description rather than its filler.
        linking_participles = frozenset(
            compositor_value("linking_participles"))
        for _i, _w in enumerate(words):
            if _i and re.sub(r"[^\w]", "", _w).casefold() in linking_participles:
                words = words[:_i]
                break
        # The first word the cap DROPS, which is the evidence for whether it
        # cut between phrases or inside one (see the convergence loop below).
        overflow = words[5] if len(words) > 5 else ""
        truncated = len(words) > 5
        words = words[:5]
        # The cap can still slice mid-phrase and leave a dangling function
        # word ("...five-foot-seven-inches with a"), which reads as broken
        # prose when this label is injected inline. Trim any trailing
        # article/preposition/conjunction/possessive so the label ends on a
        # content word.
        dangling = frozenset(compositor_value("label_dangling"))
        # One preposition over from the participle fix above: the cap can
        # also cut a phrase just AFTER the dangler took one word with it --
        # "towering hooded stranger with smooth [skin...]" keeps "with
        # smooth", which the trailing-word trim cannot see because "smooth"
        # is a content word. Only when the cap actually truncated (a phrase
        # this short cannot be judged incomplete otherwise), a dangler in the
        # tail with at most one word after it is an amputated phrase: cut
        # back to the content head. "the figure in mourning" survives when
        # nothing was truncated; a cap-cut label ends on a whole phrase.
        # ...and the two trims have to CONVERGE, because each one exposes a
        # new tail for the other. Measured live 2026-08-19, in an A/B run: "a
        # lean courier in a rain-darkened canvas coat, hair cropped short"
        # capped to "lean courier in a rain-darkened", lost "a rain-darkened"
        # to the amputated-phrase rule, and was left as "the lean courier IN"
        # -- ending on a preposition, which the comment above says in so many
        # words must not happen. Every unrecognised body in that story was
        # labelled that way, in views, in prose and in the memories written
        # from them: "the broad man in", "the old porter in". Each rule ran
        # once and neither looked at what the other uncovered. The leading
        # article strip above already knew this and used a `while`.
        # A CAP-CUT LABEL ENDS ON A WHOLE PHRASE, and the question is whether
        # the cap fell BETWEEN phrases or INSIDE one. The window that used to
        # decide it was one word wide -- an approximation tuned on a case
        # where the amputated tail happened to be short -- and it misses the
        # same shape one word longer: "a young woman with golden fox ears and
        # six golden tails" caps to "young woman with golden fox", a noun
        # phrase with its head noun cut off, kept because two words followed
        # the preposition instead of one.
        #
        # The evidence is the first word the cap DROPPED. A conjunction there
        # means the phrase we kept finished and a new one was starting, so the
        # label is whole -- "old woman with silver hair" | "and sharp eyes".
        # Anything else means the phrase runs on into the words we cut, and
        # what we kept is a fragment -- "young woman with golden fox" |
        # "ears", "lean courier in a rain-darkened" | "canvas". Then cut back
        # to the word that opened the phrase, however much of it we were
        # holding. "the figure in mourning" is untouched: nothing truncated.
        cut_inside_a_phrase = bool(truncated) and (
            re.sub(r"[^\w]", "", overflow).casefold()
            not in _ling("_BREATH_CONJUNCTIONS"))
        while True:
            before = len(words)
            while words and words[-1].lower() in dangling:
                words = words[:-1]
            if cut_inside_a_phrase:
                for _i in range(len(words) - 1, 0, -1):
                    if words[_i].lower() in dangling:
                        words = words[:_i]
                        break
            if len(words) == before:
                break
        # ...and it ends on a WORD. Stripping a quote out of "5'7\"" leaves
        # "5 7", which distinguishes nobody and reads as debris; a bare
        # measurement is not what a stranger is recognised by at a glance.
        while words and not re.search(r"[^\W\d_]", words[-1]):
            words = words[:-1]
        description = _label_safe(
            " ".join(words).rstrip(".;:").lower()).rstrip(".;:").strip()
        if description:
            return _text("unknown_actor", description=description)
    return _text("unknown_actor_fallback")

def _delivery_ok(relation, scene, observer_name, source_name, channel,
                 volume="normal", proximity=None, behind_sources=None,
                 awareness=None, senses=None):
    """Can this observer receive this source through this channel?

    Cross-seam pattern 3: the deterministic delivery paths each grew their own
    partial gate, so every one of them skipped a rule the perception model path
    honours -- the micro-loop skipped containment and graded sight, the outcome
    action backstop skipped the rear arc, the background channel skipped
    station. This is the one predicate all of them call, so a rule added here
    reaches every deterministic delivery site at once.

    `relation` is the caller's own `spatial_rel` result (built from ROOM ids,
    which only the caller can resolve uid/alias-tolerantly). Everything else is
    derived here:

    - **awareness** -- a non-awake mind receives nothing.
    - **containment** -- a sealed enclosure blocks sight AND sound, in both
      directions (`containment_conceals` is symmetric).
    - **hearing** -- `hear_level` including the `proximity` downgrade, so a
      muttered aside does not carry to an arbitrarily large room.
    - **sight/action** -- `has_visual` plus the rear-arc blind spot. An action
      is visible or it is nothing.
    - **senses** (optional) -- the observer's card senses (G4). When passed,
      the channel grade is shifted by `spatial.sense_adjusted`; None or an
      ordinary card is byte-identical to before. NOTE for callers: with an
      extraordinary-hearing card this can answer True at hearing level
      `trace`, which is DETECTION ONLY -- re-grade with sense_adjusted before
      rendering, and never deliver words or identity on a trace.
    """
    if awareness is not None and awareness in NON_AWAKE_GATED:
        return False
    # `same_subject`, not `==`, for `region_visibility`'s reason 1,800 lines
    # above: a being routinely carries a display name and an entity id at
    # once, and a bare comparison between the two answers "these are two
    # people". Here that denies a mind its OWN percept rather than handing it
    # somebody else's -- and the case where it matters most is a body sealed
    # inside something, which is concealed from every subject in the scene,
    # itself included, once the self-exemption has failed to recognise it.
    if same_subject(scene, observer_name, source_name):
        return True
    # `_enclosure_conceals`, not the bare primitive, for the same reason the
    # line above is not `==`: containment is resolved from the strings this
    # caller happened to use, and a body keyed by entity id read as a body
    # standing in the open -- so a sealed body was delivered, on every
    # channel, to everyone around whatever held it.
    if _enclosure_conceals(scene, observer_name, source_name):
        return False

    if channel == "hearing":
        level = hear_level(relation, volume, proximity=proximity)
        if senses is not None:
            level = sense_adjusted(level, "hearing", senses)
        return level != "none"

    if behind_sources and source_name in behind_sources:
        return False
    if entity_arc(scene, observer_name, source_name) == "rear":
        return False
    level = sight_level(relation)
    if senses is not None:
        level = sense_adjusted(level, "sight", senses)
    return level != "none"

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
    segments = _ling("_QUOTED_SPAN_RE").split(text)

    # ONE alternation, longest form first, so the longest name wins at every
    # position. Scripts without spaces make this load-bearing rather than
    # tidy: a name boundary cannot be asserted in Japanese (see
    # `name_boundary_pattern`), so a short unknown name like レイ would
    # otherwise eat into a longer recognised one like レイヤ. Allowed forms
    # are therefore matched too, and replaced with themselves, which shields
    # them from being partially consumed.
    candidates = []
    for src in unknown_sources:
        name = str(src.get("name") or "").strip()
        if not name or name.casefold() in allowed:
            continue
        label = _unknown_actor_label(
            name, src.get("appearance"), aliases=src.get("aliases"))
        for form in [name] + [str(a or "").strip()
                              for a in (src.get("aliases") or [])]:
            if not form or form.casefold() in allowed:
                continue
            # A short Latin form cannot be told from an ordinary word; a short
            # CJK form is a perfectly ordinary name, and skipping it is the
            # leak this whole pass exists to prevent.
            if (len(form) < 3 and len(form.split()) == 1
                    and not _UNSPACED_SCRIPT.match(form[:1])):
                continue
            if (len(form.split()) == 1
                    # Single-token names that are also everyday English words ("Rose walks in"
                    # vs "the rose garden"). For these, only the exact capitalized form is
                    # scrubbed, so ordinary lowercase prose is never mangled.
                    and form.casefold() in _ling("_COMMON_WORD_NAMES")):
                # common-word guard: exact capitalized form only
                exact = form[:1].upper() + form[1:]
                candidates.append(
                    (exact, f"(?-i:{name_boundary_pattern(exact)})", name, label))
            else:
                candidates.append(
                    (form, name_boundary_pattern(form), name, label))
    if not candidates:
        return view, []
    shields = sorted(
        {str(f or "").strip() for f in (allowed_forms or []) if str(f or "").strip()},
        key=len, reverse=True)
    ordered = sorted(candidates, key=lambda item: len(item[0]), reverse=True)
    by_group = {}
    parts = []
    for index, form in enumerate(shields):
        by_group[f"s{index}"] = None
        parts.append(f"(?P<s{index}>{name_boundary_pattern(form)})")
    for index, (_form, pattern, name, label) in enumerate(ordered):
        by_group[f"u{index}"] = (name, label)
        parts.append(f"(?P<u{index}>{pattern})")
    combined = re.compile("|".join(parts), re.IGNORECASE)

    leaked = []

    def _replace(match):
        entry = by_group.get(match.lastgroup)
        if entry is None:  # an allowed form: kept exactly as written
            return match.group(0)
        name, label = entry
        if name not in leaked:
            leaked.append(name)
        return label

    for i in range(0, len(segments), 2):  # even = outside quotes
        if segments[i]:
            segments[i] = combined.sub(_replace, segments[i])
    if not leaked:
        return view, []
    return "".join(segments), leaked

# Typographic variants folded before quote comparison. A model renders the
# same line twice with different typography -- measured live: `"I‑I must
# of..."` with U+2011 hyphens and curly apostrophes, restored a second time
# with ASCII punctuation -- and a byte-wise dedupe called them two different
# lines, so one spoken line landed twice in one view.
_TYPOGRAPHY_FOLD = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "…": "...",
})


def _fold_typography(text):
    return str(text or "").translate(_TYPOGRAPHY_FOLD)


#: The closed set `schemas.canonicalize_prose_markup` may leave in prose. It
#: is stripped for COMPARISON only -- the tags stay in the stored string,
#: which is what the reader sees rendered.
_PROSE_MARKUP_RE = re.compile(
    r"</?(i|b|u|s|mark|sup|sub|code)>", re.I)


def strip_prose_markup(text):
    """Prose as the fidelity checks must read it: words, no marks.

    The narrator emits inline emphasis unprompted -- a consequence of the
    paragraph contract teaching it that this channel speaks HTML -- and a tag
    landing INSIDE a quoted line breaks every check that looks for that line
    by substring. `"I have <i>absolutely</i> got this,"` does not contain
    `I have absolutely got this,`, so a correctly rendered line reads as a
    DROPPED one, and the narrator is sent back to rewrite prose that was
    already right.
    """
    return _PROSE_MARKUP_RE.sub("", str(text or ""))


def _contains_quote(view, quote):
    body = _fold_typography(_quote_body(quote))
    normalized_view = re.sub(
        r"\s+", " ", _fold_typography(strip_prose_markup(view)).casefold())
    normalized_body = re.sub(r"\s+", " ", body.casefold()).rstrip(".,!?…;:")
    if not normalized_body:
        return False
    # A dialogue tag changes terminal punctuation mechanically: the logged
    # line ``Lie back.`` becomes ``"Lie back," she says``.  That is the same
    # delivered quote, and treating it as absent appends a duplicate exact-line
    # injection.  Internal punctuation remains significant; only the terminal
    # mark is ignored, with a word boundary so ``back`` cannot match
    # ``backwards``.
    return re.search(
        r"(?<!\w)%s(?=$|[^\w])" % re.escape(normalized_body),
        normalized_view,
    ) is not None

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
    unspecified area" and leaking a false empty view.

    TWO PASSES, and the order is the point. `room_of` now resolves a spelling
    through the scene's entity table as well, which is what a reader holding
    only a name needs -- but this reader holds a SHEET, and a sheet is the
    better authority: it enumerates every key this character answers to, where
    the entity table may hold a stray row claiming the same display name. So
    every one of the sheet's own keys is tried against the literal ledger
    first, and identity resolution only answers for keys that found nothing.
    """
    keys = character_scene_keys(sheet)
    for key in keys:
        room = room_of(sc, key, identity=False)
        if room:
            return room
    for key in keys:
        room = room_of(sc, key)
        if room:
            return room
    return None


def _present_cast_bodies(scene, cast):
    """Every cast member the SCENE places somewhere -- [{id, name, room}].

    Presence is a fact about the world, not a judgement about the beat, and
    four readers need the same answer. Two are in `perception_act`: who is
    standing here (for `_co_present_company`) and who therefore perceives
    what happens (the perceiver list). Two more NARROW the Director's pacing
    list to it -- `runtime.build_plan` and `loops._drop_absent` -- because a
    mind the scene places nowhere gets no view, and asking it to declare
    conduct is asking a person to act from a place they are not standing in.
    It lived in `perception.py` while only that stage read it; it is here now
    for the same reason `_drop_non_awake`'s inputs are.

    Measured, chat 95 (2026-08-28): `scene.positions` held no entry for two
    of the four registered cast all run, while `flow.reactors` named them on
    turns 4, 5, 8 and 14 -- 6 `character_major` calls at 13-22s each,
    deliberating from an empty perception base, in beats whose own
    `perception_act.views` listed observers `['75']` / `['74','75']`.

    The SHEET, not `sheet_state`. Presence asks what keys this body answers
    to and where the scene puts them; the mutable per-chat state -- mood,
    goal, stance -- says nothing about it, and reading the row through
    `sheet_state` made this refuse any cast row without a ``cstate`` column.
    That is not a hypothetical: `_drop_non_awake` beside it already reads
    ``c["sheet"]`` directly for exactly this reason, and four suites build
    reactor rows of `{id, sheet}` alone.
    """
    out = []
    for c in cast or []:
        sh = json.loads(c["sheet"]) if isinstance(c["sheet"], str) else c["sheet"]
        name = character_name(sh)
        room = character_room(scene, sh)
        if name and room:
            out.append({"id": c["id"], "name": name, "room": room})
    return out


def cast_room(sc, name, cast):
    """Room of a named speaker/actor, mapping the bare name through the cast so
    a character stored under its uid/alias still resolves (the name-string
    counterpart to character_room).

    Same ordering as `character_room` and for the same reason: the literal
    ledger, then the cast, then identity -- a registered character outranks an
    entity row wearing their name."""
    room = room_of(sc, name, identity=False)
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
    return entity_room_by_name(sc, target) or room_of(sc, name)


def entity_room_by_name(sc, name):
    """Room of an UNREGISTERED scene presence, resolved from its NAME.

    `canonicalize_positions` rewrites only keys that identify a cast character
    or the player, and says so: "unregistered background presences are left
    untouched". Correct -- they are not cast -- but nothing mapped the name
    back the other way, so a presence placed under its entity uid was
    unreachable by name from the moment it was placed. Every reader that asks
    where a background speaker is got None, and `spatial_rel(None, room)`
    answers "remote, no known spatial channel".

    Measured live (chat 58, t23): a Dalek standing in the player's own alley
    with its gun-stick trained on her chest sat in `positions` under
    `40af0ac4bf2644a1`. `cast_room(sc, "A Dalek", cast)` returned None, so
    perception's hearing gate classified it as remote and dropped its line for
    every observer, and the view rendered it as "something" and "the source"
    rather than the machine she had just thrown a rock at. Corpus-wide, 47 of
    78 background lines never reached a single view.

    Name before aliases, so an alias can never outrank a real name. A name
    matching more than one entity resolves to NOBODY: two Daleks in a room are
    exactly the case this must not guess between, and a wrong room is worse
    than the None every one of them used to get.
    """
    target = str(name or "").strip().lower()
    entities = (sc or {}).get("entities")
    if not target or not isinstance(entities, dict):
        return None
    positions = (sc or {}).get("positions")
    positions = positions if isinstance(positions, dict) else {}
    pos_ci = {str(k).strip().lower(): v for k, v in positions.items()}

    def _match(by_alias):
        hits = []
        for eid, ent in entities.items():
            if not isinstance(ent, dict):
                continue
            if by_alias:
                forms = {str(a).strip().lower() for a in (ent.get("aliases") or [])}
            else:
                forms = {str(ent.get("name") or "").strip().lower()}
            if target in forms - {""}:
                hits.append(eid)
        return hits[0] if len(hits) == 1 else None

    eid = _match(False) or _match(True)
    if not eid:
        return None
    # The uid is the position key in practice; an entity may also carry its own
    # `room`, which is authoritative only when no position exists for it.
    room = pos_ci.get(str(eid).strip().lower())
    if room is None:
        room = pos_ci.get(target)
    if room is None:
        ent = entities.get(eid) or {}
        room = ent.get("room")
    return room or None

def cast_spelling_policy(cast, player_name=None, *, aliases=True):
    """Which spelling each registered cast body answers to, and what it is.

    ONE POLICY, because the two hand-rolled copies of it disagreed and the
    disagreement is a live defect. `canonicalize_positions` matched a sheet
    name and uid and deliberately refused aliases; `_heal_attire_identity_keys`
    matched aliases too. So in chat 82 ("Sarah Moon -- Hinami attempt 2") the
    same body came out spelled two ways at once: `attire` folded
    "Dr. Sarah Moon" onto the sheet's "Sarah Moon" and `positions` did not,
    leaving one woman keyed two ways across the ledgers that describe her.

    `aliases` is the one setting, and the two callers genuinely differ on it.
    Attire is keyed by BODIES only, so an alias there can name nothing else
    and matching it heals a real split. `positions` keys objects, fixtures and
    unregistered presences beside people, where a generic alias ("The Oncoming
    Storm") could collide with a separate entity and move an object into a
    person -- so that caller passes `aliases=False`. The difference used to be
    two hand-rolled tables that disagreed by accident; it is now one table with
    the disagreement written down.

    Returns (canonical, forms) --
      `canonical(spelling)`: the sheet name this spelling belongs to, or the
        spelling unchanged when it belongs to nobody registered. Objects,
        fixtures and unregistered background presences are never touched:
        they are not cast, and rewriting them is what broke carried lights
        and destruction cascades the first time somebody folded on identity
        alone.
      `forms`: {casefolded spelling -> sheet name} for callers that need the
        table rather than the function.

    THE AUTHORITY IS THE SHEET, per `DESIGN_SUBJECT_SPELLING_AUTHORITY.md`.
    A sheet is authored, durable, and locked against rekeying; a scene entity
    record is minted by a model on turn 0 and is provisional until commit
    validates it. Letting a model's incidental honorific become a being's
    canonical name inverts the source-of-truth order.

    Two guards, both paid for:

    - A NAME OUTRANKS SOMEBODY ELSE'S ALIAS FOR IT. One character's alias is
      another's name often enough in fiction -- a nickname, a family name, a
      title. Measured: with a character named Yuki and a second whose aliases
      include "Yuki", folding on the alias collapsed Yuki's wardrobe onto the
      other woman, who was wearing nothing and acquired a yukata; Yuki's own
      record disappeared.
    - AMBIGUITY RESOLVES TO NOTHING. A spelling two cast members answer to is
      registered for neither. Folding two beings into one is strictly worse
      than leaving two spellings of one.
    """
    own_names, claims = set(), {}
    rows = []
    for row in cast or []:
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        ident = normalize_character_data(sheet).get("identity", {})
        name = str(ident.get("name") or character_name(sheet) or "").strip()
        if not name:
            continue
        try:
            rid = row["id"]
        except Exception:
            rid = None
        # The uid is an IDENTIFIER, not a name somebody else could also go by,
        # so it rides regardless of `aliases` -- reading it out of identity
        # rather than off `character_scene_keys`'s index 1, which is the uid
        # only when the sheet has one and the first alias when it does not.
        rows.append((name, str(ident.get("uid") or "").strip(),
                     [str(a or "").strip()
                      for a in (ident.get("aliases") or []) if str(a or "").strip()],
                     rid))
        own_names.add(name.casefold())

    def _claim(spelling, canon):
        text = str(spelling or "").strip()
        if not text:
            return
        folded = text.casefold()
        if claims.get(folded, canon) != canon:
            claims[folded] = None          # two beings: registered for neither
        else:
            claims[folded] = canon

    for canon, uid, alias_list, rid in rows:
        _claim(canon, canon)
        if uid:
            _claim(uid, canon)
        if rid is not None:
            _claim(f"character:{rid}", canon)
        for alias in (alias_list if aliases else []):
            if alias.casefold() in own_names \
                    and alias.casefold() != canon.casefold():
                continue               # a real name outranks an alias for it
            _claim(alias, canon)
    if player_name:
        _claim(player_name, player_name)
        _claim("character:player", player_name)

    forms = {k: v for k, v in claims.items() if v}
    # The alphanumeric fold `canonicalize_positions` has always applied, so
    # "Dr. Moon" still answers to a key written "drmoon". Second, so a literal
    # spelling always wins over a squashed one.
    squashed = {}
    for spelling, canon in forms.items():
        norm = re.sub(r"[^a-z0-9]", "", spelling)
        if norm and norm not in forms:
            squashed.setdefault(norm, canon)

    def canonical(name):
        text = str(name or "").strip()
        if not text:
            return name
        folded = text.casefold()
        return (forms.get(folded)
                or squashed.get(re.sub(r"[^a-z0-9]", "", folded))
                or name)

    return canonical, forms


def _cast_entity_claims(scene, cast, player_name=None):
    """({entity id -> the cast sheet name it IS}, forms), for the entities
    that unambiguously belong to exactly one registered character.

    ONE RESOLUTION, TWO WRITERS. `reconcile_cast_entity_names` renames what it
    finds; `stamp_authored_interiors` stamps the card's authored topology onto
    it. They ask the identical question -- which scene entity is this sheet's
    body -- and answering it twice is how two copies of one rule start to
    disagree, which is the defect `cast_spelling_policy` itself exists to have
    ended.

    TWO ENTITIES ANSWERING TO ONE CAST MEMBER CLAIM NEITHER. That is two
    records for one being -- a real defect, but a MERGE one
    (`_dedup_duplicate_entity_keys`); writing to both here would mint the
    duplicate the merge exists to collapse, and writing to one would pick a
    winner on nothing.
    """
    entities = (scene or {}).get("entities")
    if not isinstance(entities, dict):
        return {}, {}
    canonical, forms = cast_spelling_policy(cast, player_name)
    if not forms:
        return {}, {}
    registered = {str(v).casefold() for v in forms.values()}

    def belongs_to(entity, eid):
        """The cast member this entity IS, or None. Asked of a spelling it
        already answers to correctly as well as one it does not: an entity
        named right can still carry an alias that is somebody else's name."""
        for spelling in (eid, entity.get("name"),
                         *(entity.get("aliases") or [])):
            found = canonical(spelling)
            if str(found or "").strip().casefold() in registered:
                return found
        return None

    owned, claimed = {}, {}
    for eid, entity in entities.items():
        if not isinstance(entity, dict):
            continue
        canon = belongs_to(entity, eid)
        if not canon:
            continue
        owned[eid] = canon
        claimed.setdefault(canon, []).append(eid)
    return ({eid: canon for eid, canon in owned.items()
             if len(claimed.get(canon) or []) == 1}, forms)


def stamp_authored_interiors(scene, cast, player_name=None):
    """Put each cast card's authored inside on the scene entity that IS it.

    THE CARD IS NOT IN THE MERGE'S SCOPE. `materialize_enclosure_interiors`
    runs inside `merge_scene_with_diff`, which is handed a scene and a diff
    and has no cast, no sheets and no way to reach them -- so the topology an
    author declared has to be scene-resident before the merge reads it. This
    is the one seam that carries it across, and it runs at commit beside
    `reconcile_cast_entity_names`, on both the standing scene and this beat's
    diff, so a holder the Director just minted is stamped from its first beat.

    NEVER A RETRACTION, and never anything but this one key. An empty card
    section removes nothing -- clearing a sheet field is not a statement about
    a body already standing inside one -- and name, aliases, keys, rooms and
    positions are somebody else's to write. Idempotent, which is what lets a
    checkpoint restore replay it.

    Returns the entity ids it stamped, for the caller's report.
    """
    entities = (scene or {}).get("entities")
    if not isinstance(entities, dict):
        return []
    authored = {}
    for row in cast or []:
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        interior = character_body_interior(sheet)
        if not interior:
            continue
        name = str(normalize_character_data(sheet).get(
            "identity", {}).get("name") or "").strip()
        if name:
            authored[name.casefold()] = interior
    if not authored:
        return []
    claims, _forms = _cast_entity_claims(scene, cast, player_name)
    stamped = []
    for eid, canon in claims.items():
        interior = authored.get(str(canon).strip().casefold())
        if not interior:
            continue
        entity = entities[eid]
        if entity.get("interior_spec") == interior:
            continue
        entity["interior_spec"] = interior
        stamped.append(str(eid))
    return stamped


def reconcile_cast_entity_names(scene, cast, player_name=None):
    """Make `canonical_subject_map`'s assumption TRUE for cast-mirrored bodies.

    That function folds every spelling of a being onto the ENTITY's own
    `name`, on the stated ground that "for a mirrored cast member [it] IS the
    display name every reader already expects". Live in chat 82 it was not:
    the sheet said "Sarah Moon" and the Director minted the entity as
    "Dr. Sarah Moon", one of her aliases -- so the scene's idea of her
    canonical name pointed away from the one perception, character, narration
    and psychology all address her by.

    The fix is not a different fold direction. It is to reconcile the record
    the fold reads, at the seams that already hold the cast: an entity that
    unambiguously answers to exactly one registered character is renamed to
    that character's sheet name, and the spelling it loses is demoted to an
    ALIAS so prose and lookups written the old way still resolve.

    THE ENTITY KEY IS NEVER TOUCHED. Carried lights, derived stations and
    destruction cascades resolve by entity id, and renaming id-keyed rows is
    exactly what cost eleven tests the first time identity folding was tried
    (`spatial_identity.canonical_subject_map`'s G3 comment). Only `name` and
    `aliases` move.

    Idempotent, and it must stay so: it runs on the standing scene at every
    commit, which is what heals a save written before this rule existed, and
    a checkpoint restore replays it.

    Returns [(entity_id, old_name, new_name)] for warnings; empty when
    nothing needed saying, which is the common case.
    """
    entities = (scene or {}).get("entities")
    if not isinstance(entities, dict):
        return []
    claims, forms = _cast_entity_claims(scene, cast, player_name)
    renamed = []
    for eid, canon in claims.items():
        entity = entities[eid]
        old = str(entity.get("name") or "").strip()
        aliases = [str(a).strip() for a in (entity.get("aliases") or [])
                   if str(a or "").strip()]
        # An alias that belongs to ANOTHER cast member is not this body's to
        # answer to -- the Yuki guard, applied to the record rather than only
        # to the lookup, because the merge fold reads the record and has no
        # cast to consult. An alias nobody registered is left alone: it names
        # no other body, so it cannot steal one.
        aliases = [a for a in aliases
                   if forms.get(a.casefold(), canon) == canon]
        if old and old.casefold() != canon.casefold() \
                and old.casefold() not in {a.casefold() for a in aliases}:
            aliases.append(old)
        aliases = [a for a in aliases if a.casefold() != canon.casefold()]
        if entity.get("name") == canon and aliases == (entity.get("aliases")
                                                       or []):
            continue                                    # already reconciled
        entity["name"] = canon
        entity["aliases"] = aliases
        if old and old != canon:
            renamed.append((str(eid), old, canon))
    return renamed


def canonicalize_positions(positions, cast, player_name=None):
    """Rewrite any positions key that identifies a registered cast character
    (or the player) to that person's display name -- the positions-key
    convention every reader (perception, commit, spatial) expects. Non-person
    keys (objects, unregistered background presences) are left untouched.

    Recognizing `character:<id>` and the player is load-bearing: the director
    model keys the SAME person by different schemes across a turn (Data as
    `character:29` here, `Lt. Commander Data` there), and without collapsing
    them to one canonical key the person acquired TWO position entries in
    conflicting rooms -- observed live, Data was simultaneously on the bridge
    (`character:29`) and in a corridor (`Lt. Commander Data`), so name-lookup
    resolved him to the corridor and perception rendered his bridge station as
    empty. Collapsing to a single key makes a later move update the one entry.

    ALIASES ARE STILL REFUSED HERE, and that is now a stated setting rather
    than a second table. `positions` keys objects and unregistered presences
    beside people, so a generic alias could name a genuinely separate entity
    and folding it would move an object into a person. `commit`'s attire heal
    accepts aliases because attire keys only bodies -- and the two disagreeing
    by accident is what left chat 82's Sarah Moon spelled "Sarah Moon" in
    `attire` and "Dr. Sarah Moon" in `positions` at the same time. The cure for
    that is `reconcile_cast_entity_names`, which fixes the ENTITY record so the
    merge fold spells every ledger the same way, not a wider match here.
    """
    if not isinstance(positions, dict):
        return {}
    if not cast and not player_name:
        return positions
    canonical, forms = cast_spelling_policy(cast, player_name, aliases=False)
    if not forms:
        return positions
    result = {}
    for key, room in positions.items():
        result[canonical(key)] = room
    return result

def _append_micro_view(base_view, additions):
    parts = [str(base_view or "").strip()]
    parts.extend(str(item).strip() for item in additions if str(item or "").strip())
    return "\n\n".join(part for part in parts if part)

# Defined in `persist/commit_common.py` and imported through the `commit`
# facade rather than copied: this module and commit both run it, on the model's
# output and on a rehydrated result respectively, and two copies of one shape
# normalisation is how the two come to disagree about what a legacy field
# means (audit STORY-F11's shape). The direction is forced by an import cycle
# -- see that function's docstring.
from persist.commit import _normalize_character_output  # noqa: E402,F401


def declared_goal(result):
    """The goal one character result declares, derived from the enacted want.

    The output template no longer asks for `active_state.goal`: commit was
    measured (401 recent-era calls, 2026-08-11 audit + re-measure) replacing
    the emitted string with `wants[enacted].want` on 99.0% of calls, and the
    two matched only 16.2% of the time -- the field was ~20 tokens/call of
    decode-time cost carrying a worse copy of an answer the result already
    contains. Every reader of the raw variant/result field derives it here
    instead, with the legacy field as the fallback so pre-change stored
    variants -- and any provider that still emits it -- read identically.
    """
    if not isinstance(result, dict):
        return ""
    active = result.get("active_state")
    if not isinstance(active, dict):
        return ""
    wants = active.get("wants")
    enacted = active.get("enacted_want")
    if (isinstance(wants, list) and isinstance(enacted, int)
            and 0 <= enacted < len(wants) and isinstance(wants[enacted], dict)):
        want = str(wants[enacted].get("want") or "").strip()
        if want:
            return want
    return str(active.get("goal") or "").strip()

# Narration ABOUT an utterance, as opposed to the utterance. A player writes
# their own beat in second person ("you gently take her by the wrist"), so a speech
# text carrying `you`/`your` outside its quotes is prose the interpreter lifted
# whole rather than the line the player spoke. Attribution verbs are kept
# deliberately narrow -- `say`/`said` and friends, never `tell`/`told` -- so an
# ordinary spoken line that happens to quote someone ('He told me "get out" and
# I left.') is not mistaken for narration and gutted.


def repair_narrated_speech(text):
    """Reduce a speech text that swallowed its own narration to the words said.

    Observed live: `director_interpret` returned the player's ENTIRE raw input
    as a single speech element, stage directions included --

        '"Wait" You say it flatly, without turning around. "I am not going."'

    -- and perception injected it faithfully as dialogue. Two failures follow
    at once: the narration is delivered as spoken words, and because the lifted
    prose is in second person, the "You" now points at the LISTENER, who is
    told they said it.

    Fires only when the text holds at least one quoted span AND the residue
    outside those spans reads as narration (>=2 words, carrying a second-person
    pronoun or a speech-attribution verb). A wholly unquoted line -- the normal
    shape -- is returned untouched, as is a line that is nothing but its quote.
    Returns the input unchanged when it declines to act, so callers may assign
    the result unconditionally.
    """
    raw = str(text or "")
    if not raw.strip():
        return text
    segments = _ling("_QUOTED_SPAN_RE").split(raw)
    # split() alternates residue/span/residue...; odd indices are the spans.
    spans = [s for i, s in enumerate(segments) if i % 2 == 1]
    if not spans:
        return text
    residue = " ".join(s for i, s in enumerate(segments) if i % 2 == 0)
    if len(residue.split()) < 2 or not _ling("_SPEECH_NARRATION_RE").search(residue):
        return text
    bodies = [b for b in (_quote_body(s) for s in spans) if b]
    if not bodies:
        return text
    spoken = ""
    for body in bodies:
        if spoken and spoken[-1] not in ".!?,;:-—":
            spoken += "."
        spoken = f"{spoken} {body}" if spoken else body
    return spoken


def repair_narrated_speech_elements(out):
    """Apply `repair_narrated_speech` to one interpret result in place.

    Covers both representations -- the `sequence` speech elements and the flat
    `speech` mirror -- because downstream stages read whichever is present.
    Returns the list of (before, after) pairs it changed, for warning.
    """
    changed = []
    if not isinstance(out, dict):
        return changed
    for element in (out.get("sequence") or []):
        if not isinstance(element, dict) or element.get("type") != "speech":
            continue
        before = element.get("text")
        after = repair_narrated_speech(before)
        if after != before:
            element["text"] = after
            changed.append((before, after))
    before = out.get("speech")
    if before:
        after = repair_narrated_speech(before)
        if after != before:
            out["speech"] = after
            if not any(b == before for b, _ in changed):
                changed.append((before, after))
    return changed


def player_speech_lines(interp):
    lines = [e.get("text") for e in (interp.get("sequence") or [])
             if e.get("type") == "speech" and e.get("text")]
    if not lines and interp.get("speech"):
        lines = [interp["speech"]]
    return lines


# Leading words that are not the name itself. Splitting a name on whitespace
# and taking token 0 matched "The" for a player called "The Stranger", which
# then matched almost every sentence in the beat.


def _player_name_forms(player_name):
    """Sentence-opening forms that identify the player: the full name, plus any
    single word of it substantial enough to stand alone."""
    name = str(player_name or "").strip()
    if not name:
        return []
    forms = [name]
    for clean in _name_tokens(name):
        # The capital is what separates a name part from an ordinary word it
        # sits beside -- in a script that HAS capitals. A caseless script
        # offers no such signal, and demanding one there is how a Japanese
        # player name contributed no standalone form at all; the leader list
        # and the length floor carry it instead.
        if len(clean) < _name_token_floor(clean):
            continue
        if not clean[:1].islower() \
                and clean.casefold() not in _ling("_NAME_LEADERS"):
            forms.append(clean)
    # Longest first so "The Stranger" is preferred over "Stranger".
    return sorted(set(forms), key=len, reverse=True)


#: Bounded, because this is the file's one piece of mutable module state and it
#: is keyed by NAME FORM -- so it grows with every cast of every chat the
#: process has served, and nothing ever cleared it. An LRU is the right shape:
#: the working set is one scene's cast, and a form that falls out is recompiled
#: in microseconds.
_SUBJECT_OPENER_CACHE = 512


@lru_cache(maxsize=_SUBJECT_OPENER_CACHE)
def _subject_opener(form):
    """Does a sentence OPEN with this name, as subject or possessive?

    Tolerates a LEADING ARTICLE, because the article belongs to the prose and
    not to the name. A body registered as "A Dalek" is written "The Dalek" the
    moment it stops being new, and the article is the only difference -- the
    same trap `docs/UNBUILT.md` §1.17 documents for presence identity. Without
    this every subject-anchored guard silently missed such a body: live
    (chat 58, t28) the Dalek's own view read "The Dalek's visual sensors pick
    up...", "The Dalek hears...", "The Dalek's own base grinds forward" --
    third person about its own perceiver, straight past `_strip_self_narration`,
    whose forms were "A Dalek" and "Dalek" and neither of which opens that
    sentence.

    Articles, and a TITLE STANDING IMMEDIATELY BEFORE THE NAME. The two are
    not the same admission and the line between them is where §1.17 draws it:
    a title used INSTEAD of a name is frequently the only thing telling two
    bodies apart ("the guard" is not "the captain"), and that is still
    refused -- `_NAME_LEADERS` cannot open a sentence on its own here. A title
    used BEFORE a name adds nothing to identify and cannot confuse anybody,
    because the name still has to match right behind it.

    Found by the abbreviation repair (`split_sentences`). Before it, "Dr.
    Watson watches the door" reached this function already broken in half, so
    the second piece opened with the bare name and the guard fired by
    accident -- leaving a dangling "Dr." where the cut had been. Repairing the
    split correctly would otherwise have handed the sentence back whole and
    lost the catch, turning one visible defect into a silent one.

    The name itself keeps its case sensitivity: a capitalised form matches
    case-sensitively as before, so an ordinary noun that happens to spell a
    name does not bind.
    """
    # `name_boundary_pattern`, not a trailing `\b`: `\b` asserts a
    # transition between word and non-word characters, which describes
    # scripts that space their words and nothing else. A Japanese particle
    # is a word character, so 「ヒナミは」 never matched `ヒナミ\b` -- and
    # this is the primitive every subject-anchored guard in the file is
    # built on, so all of them, player-act authority included, resolved
    # NOBODY as the subject of any sentence in such a story. The boundary
    # the pattern does apply still refuses a Latin name inside a longer
    # word ("Hinamis"), and the leading article stays this function's own
    # rule.
    titles = sorted((t for t in _ling("_NAME_LEADERS")
                     if t.strip(".").casefold() in _ling("_NAME_TITLE_TOKENS")
                     and t.strip(".").casefold() not in ("a", "an", "the")),
                    key=len, reverse=True)
    # Inline-insensitive: the name itself keeps this function's case rule, and
    # a title never carries identity, so "Dr." and "dr." are the same word.
    lead = "|".join(re.escape(t) for t in titles)
    return re.compile(
        rf"^(?:(?i:{lead})\s+)?(?:[Tt]he\s+|[Aa]n?\s+)?"
        rf"{name_boundary_pattern(form)}(?:['’]s)?",
        re.I if form[:1].islower() else 0)


def _ends_with_abbreviation(piece, abbreviations):
    """Does this fragment end in an abbreviation's full stop rather than a
    sentence's? The last whitespace-delimited token, minus any closing
    punctuation around it, stripped of its trailing period."""
    token = str(piece or "").strip().split()[-1:] or [""]
    word = token[0].strip("\"'“”‘’()[]")
    if not word.endswith("."):
        return False
    return word[:-1].casefold() in abbreviations


def split_sentences(text, split=None):
    """Sentences, with an abbreviation's period not mistaken for a full stop.

    Every splitter in this tree breaks on `.` followed by whitespace, and a
    title is a period followed by whitespace. So "occupied by Dr. Sarah Moon."
    is TWO sentences: one ending "...by Dr.", and a fragment that is nothing
    but a name.

    That is not cosmetic where a sentence is the unit a guard decides about.
    `_strip_self_narration` drops whole sentences whose subject is the
    perceiver, and the fragment IS the perceiver -- so it was dropped and the
    honorific left dangling. Live, chat 82: Sarah Moon's own view of her own
    room read "The observation chair is occupied by Dr." The identical note
    written without the title is untouched, because then her name sits inside
    a real sentence and no whole sentence is only her.

    The token set is language pack data (`_SENTENCE_ABBREVIATIONS`), because
    "a period may end an abbreviation" is a fact about a WRITING SYSTEM, not
    about a story -- Japanese ends its sentences with `。` and has nothing here
    to protect.

    Deliberately NOT every abbreviation: "etc." and "Ph.D." genuinely end
    sentences, and rejoining there would weld two real ones together. What is
    in the set is the class that essentially never ends a sentence -- titles
    and name particles, which are also the class that appears immediately
    before a NAME, which is what makes the split damaging in the first place.
    """
    pattern = split if split is not None else _SENTENCE_SPLIT
    abbreviations = _ling("_SENTENCE_ABBREVIATIONS")
    out = []
    for piece in pattern.split(str(text or "")):
        if piece is None:
            continue
        if out and out[-1].strip() and _ends_with_abbreviation(
                out[-1], abbreviations):
            out[-1] = f"{out[-1].rstrip()} {piece.lstrip()}"
        else:
            out.append(piece)
    return out


def _sentence_subjects(prose, names, split=None):
    """Each sentence of `prose` paired with the name that is plainly its subject.

    The version this replaced refused to resolve pronouns at all, on the
    ground that "She lifts it" could be anyone in the beat. That is true of
    a pronoun read in ISOLATION and false of one read in sequence: prose
    establishes a subject by name and then continues it, which is why the
    live miss (chat 56 t1391) slipped through -- the Director named the Doctor
    once, then wrote four more sentences about him as "he", and a check that
    only reads sentence-opening names saw only the one legitimate sentence.

    So: track the most recently NAMED subject and let a pronoun-subject
    sentence continue it. A new named subject takes over, which is what keeps
    this honest -- "The Doctor draws it. Hinami flinches. She says nothing."
    binds the pronoun to Hinami, not to the Doctor. Where no name has been
    established yet, the pronoun binds to nobody rather than to a guess.

    Yields (sentence, subject_name_or_None) in order.

    `split` overrides the sentence splitter for callers that need a different
    one -- perception's tolerates a closing quote between the terminal
    punctuation and the space, and losing that would silently make a whole
    passage one "sentence" again.
    """
    current = None
    pieces = split_sentences(
        prose or "",
        split if split is not None else re.compile(r"(?<=[.!?])\s+"))
    for sentence in pieces:
        stripped = sentence.strip()
        if not stripped:
            continue
        matched = None
        for cand in (names or []):
            for form in _player_name_forms(cand):
                if _subject_opener(form).match(stripped):
                    matched = cand
                    break
            if matched:
                break
        if matched:
            current = matched
            yield stripped, matched
        elif _ling("_SUBJECT_PRONOUN_RE").match(stripped):
            yield stripped, current
        else:
            yield stripped, None


# A conjunct that introduces its OWN subject is not the tracked body's doing.


def _predicate_heads(tail, window):
    """The head words of each conjunct of a predicate.

    One subject governs several verbs -- "takes a half-step closer, hands open
    at his sides, and speaks in a low, steady voice" is one body doing two
    things -- so a window measured from the NAME sees only the first verb and
    the second escapes. That is exactly how the live case slipped past: the
    attribution verb sat twelve words past the subject, and the window is
    three. Measuring the window from each conjunct instead keeps the check on
    what this body is DOING (rather than any word anywhere in a long sentence)
    while letting it reach the later verbs of a compound predicate.

    Conjuncts that introduce their own subject are dropped: in "The Doctor
    lowers the device, and she says nothing" the saying is hers.

    Returns (head, clause) pairs -- the head for verb matching, the whole
    clause for tests that read wider than the verb (see `_PROXIMITY_RE`).
    """
    heads = []
    for part in re.split(r",|\band\b|\bthen\b|;", tail or "", flags=re.I):
        part = part.strip()
        if not part or _ling("_NEW_SUBJECT_RE").match(part):
            continue
        heads.append(
            (" ".join(re.findall(r"[A-Za-z']+", part)[:window]), part))
    return heads


def _strip_subject(sentence, name):
    """A sentence's predicate: everything past its subject, whether that
    subject was written as the name or as a pronoun continuing it."""
    for form in _player_name_forms(name):
        match = re.match(rf"^{re.escape(form)}(?:'s)?\b", sentence)
        if match:
            return sentence[match.end():]
    match = _ling("_SUBJECT_PRONOUN_RE").match(sentence)
    return sentence[match.end():] if match else ""


# How far past the name to look for the verb. Same window the player check
# uses, and for the same reason: the act must be what this body is DOING, not
# a word appearing anywhere in a long sentence.
_SPEECH_VERB_WINDOW = 3


def _check_character_speech_authority(resolved_event, silent_names,
                                      other_names=()):
    """Speech a resolved_event gives a character who declared none this beat.

    The mirror of `_check_player_act_authority`, and the boundary it defends is
    the same one from the other side. Live, alpha 6.0.2: a character agent
    declared silence -- empty sequence, `stop_reason: "natural silence"`, no
    dialogue_log entry -- and the resolved_event said "<the character> adds a
    further comment" anyway. Perception rendered a speech event with no
    content; the narrator, having nothing to quote, dressed the absence as
    inaudibility. It read as a muffling bug and was a fabrication.

    A character owns their own speech exactly as the player owns theirs, and
    until now only the player had a guard. Nothing objected when the Director
    authored conduct for a mind that owns it.

    Scoped like its sibling, to the unambiguous case: the character was ASKED
    this beat and declared NO speech at all, so any utterance attributed to
    them is invented by construction. Sentence subject must be the name
    itself -- a pronoun subject could be anyone in the beat, and guessing
    would make this cry wolf on ordinary narration.

    `silent_names` is who declared nothing; a character who spoke is not
    checked, because separating an elaborated line from an added one needs
    more than a verb list.

    Subject resolution is pronoun-continuation-aware (`_sentence_subjects`)
    and the verb window is measured per conjunct (`_predicate_heads`). Both
    were added after chat 56 t1391, where the guard was armed and silent: the
    Director wrote the fabrication as "He takes a half-step closer, hands open
    at his sides, and speaks in a low, steady voice", which the original
    name-anchored, three-words-from-the-name check could not see at all.
    """
    warnings = []
    all_names = list(silent_names or []) + list(other_names or [])
    for sentence, subject in _sentence_subjects(resolved_event, all_names):
        if subject is None or subject not in (silent_names or []):
            continue
        # A quoted span is `_check_prose_quote_authority`'s business, not
        # this one: what this catches is the contentless attribution a quote
        # check cannot see -- "X adds a comment" quotes nothing, so nothing
        # downstream can tell it was invented.
        without_quotes = _ling("_NARRATION_QUOTE_RE").sub(" ", sentence)
        tail = _strip_subject(without_quotes, subject)
        for head, _clause in _predicate_heads(tail, _SPEECH_VERB_WINDOW):
            if re.search(cue_boundary_pattern(_ling("_ATTRIBUTION_VERBS")), head, re.I):
                warnings.append(
                    "Speech attributed to a character who declared none "
                    f"(character-speech authority): {subject}: "
                    f"{sentence[:120]!r}"
                )
                break
    return warnings


def _check_character_act_authority(resolved_event, declared_actions, name,
                                   other_names=()):
    """Physical acts a resolved_event gives a CHARACTER they did not declare.

    The third side of the same boundary `_check_player_act_authority` and
    `_check_character_speech_authority` defend, and the one nothing guarded:
    act authority was enforced for the player only, so a character could be
    handed conduct freely. Live, chat 56 t1391: the Doctor declared a scan
    "from several feet away", "while staying at distance", and the resolve had
    him take "a half-step closer". The narrator dropped it, so it was invisible
    in play -- and it still committed as his own episodic memory of what he did.

    Two scopes, because the two cases admit different certainty:

    * The character declared NO action at all. Silence about conduct is a
      declaration, so any act is invented by construction -- the full act-verb
      list applies, exactly as for the player.

    * The character declared actions, none of them locomotive. Elaborating a
      declared act is the Director's job and is NOT flagged; separating
      elaboration from addition in general needs more than a verb list, so
      this narrows to the one addition that is unambiguous and consequential:
      MOVEMENT. A character who declared no movement was not moved.
    """
    if not name:
        return []
    declared_text = " ".join(
        f"{a.get('attempt', '')} {a.get('observable', '')}"
        for a in (declared_actions or []) if isinstance(a, dict)
    )
    if declared_actions:
        # Already moving under their own declaration: the Director may render
        # that movement however it likes.
        # Verbs that change where a body IS or how far it is from someone else. The
        # Director may render a declared act richly; it may not relocate a character
        # who declared no movement, because distance is load-bearing -- it decides
        # what perception delivers, what contact is possible, and (chat 56 t1391) it
        # can directly reverse the intent the character declared, which was to scan
        # her "without crowding her".
        #
        # Movement is not always written as a locomotion VERB. The live case wrote it
        # as a verb plus a distance noun -- "takes a half-step closer" -- whose head
        # verb is "take", which is no more locomotive than taking a screwdriver. What
        # marks it as movement is the distance word, so read the clause for one.
        if re.search(cue_boundary_pattern(_ling("_LOCOMOTION_VERBS")), declared_text, re.I):
            return []
        verbs, kind, proximity = (
            _ling("_LOCOMOTION_VERBS"), "undeclared movement", True)
    else:
        # Verb STEMS a resolved_event uses when it gives someone an ACT, matched with
        # ordinary English inflection (-s/-es/-ed/-ing) so "straightens", "shifting"
        # and "reached" all count. Kept to unambiguous bodily/manipulative verbs: this
        # exists to catch the player being handed conduct they never declared, not to
        # police prose.
        verbs, kind, proximity = _ling("_PLAYER_ACT_VERBS"), "act not declared", False

    warnings = []
    all_names = [name] + [n for n in (other_names or []) if n != name]
    for sentence, subject in _sentence_subjects(resolved_event, all_names):
        if subject != name:
            continue
        without_quotes = _ling("_NARRATION_QUOTE_RE").sub(" ", sentence)
        tail = _strip_subject(without_quotes, subject)
        for head, clause in _predicate_heads(tail, 3):
            if re.search(rf"\b(?:{verbs})\b", head, re.I) or (
                    proximity and _ling("_PROXIMITY_RE").search(clause)):
                warnings.append(
                    f"Character {kind} this beat (character-act authority): "
                    f"{name}: {sentence[:120]!r}"
                )
                break
    return warnings


# Below this, a quoted span is a label or a scare quote rather than an
# utterance -- a readout reading "STABLE", the word "safe".
_PROSE_QUOTE_MIN_WORDS = 3


def _check_prose_quote_authority(resolved_event, allowed_bodies):
    """Spoken lines in resolved_event PROSE that nobody declared.

    The dialogue_log backstop (director.py) drops a director-invented line for
    a registered character by comparing its `exact_quote` against that
    character's own declaration. It is a good guard and it was inert in chat 56
    t1391, because `dialogue_log` was EMPTY: the invented line existed only in
    the resolved_event prose. The speech check meanwhile strips quoted spans on
    the stated assumption that the dialogue path covers them. Each guard
    assumed the other held the ground, and a quote in prose with no log entry
    fell between them.

    This closes it from the other side, and needs no subject resolution to do
    it: a line nobody declared is invented no matter WHO the prose says said
    it. `allowed_bodies` is every quote body that was legitimately declared
    this beat -- by the player, by any character, or by an unsheeted background
    presence the Director is licensed to voice.
    """
    warnings = []
    seen = set()
    # Words only, for the same reason the player-echo strip needs it: the
    # Director RE-PUNCTUATES a line it is quoting, and an exact membership
    # test then reads its own faithful rendering as an invention.
    folded_allowed = [_echo_fold(a) for a in (allowed_bodies or ()) if _echo_fold(a)]
    # Quoted spans, in every style the resolve model actually produces. The single
    # -quote form must not mistake an apostrophe for a delimiter, so a quote may
    # only OPEN where no letter precedes it and CLOSE where no letter follows --
    # which leaves "You're" intact inside the span.
    for pattern in _ling("_PROSE_QUOTE_RES"):
        for span in pattern.findall(resolved_event or ""):
            body = _quote_body(span)
            if not body or body in seen:
                continue
            seen.add(body)
            if len(re.findall(r"[A-Za-z']+", body)) < _PROSE_QUOTE_MIN_WORDS:
                continue
            if body in allowed_bodies:
                continue
            # A quote NESTED inside a declared line is not a new utterance --
            # it is somebody quoting what was already said. The four patterns
            # above each sweep the whole prose independently, so a declared
            # line carrying inner quotes ('And I said "ask me again" -- not
            # "yes, absolutely, show you the stars."') yields the outer span
            # AND both inner ones, and only the outer could ever match.
            #
            # Measured across the live corpus: 14 flags, 13 of them cleared by
            # this test -- a 93% false-positive rate on a guard whose every
            # firing costs a full second Director call, the most expensive
            # correction this seam can order.
            #
            # ONE DIRECTION ONLY: the flagged span must sit INSIDE something
            # that was declared. The reverse -- a declared line sitting inside
            # the flagged span -- is prose that EXPANDED on what somebody said,
            # which is the invention this guard exists to catch, and allowing
            # it cleared the one genuine case in the corpus along with the
            # thirteen false ones.
            folded = _echo_fold(body)
            if folded and any(folded in a for a in folded_allowed):
                continue
            warnings.append(
                "Spoken line in resolved_event that nobody declared "
                f"(prose-quote authority): {body[:120]!r}"
            )
    return warnings


# WHAT THE DIRECTOR MAY STILL SPEAK FOR.
#
# Measured 2026-08-08 across the whole corpus: background lines authored in
# `director_resolve` run a MEDIAN OF 8 WORDS against the sheeted cast's 16, and
# 27% of them are four words or fewer against the cast's 13% -- "Dragon
# Kingdom...", "Kadomon.", "Sorry-sorry-". 2,042 of the 2,240 background lines
# in the corpus came from the Director; the stage built to voice extras
# produced 200, because `pick_background_reactors` is a BACKSTOP that stands
# down whenever the Director already spoke for someone.
#
# So the model adjudicating physics, dialogue order, state diffs and time in
# one pass was also writing every extra's dialogue, as filler, with no
# perception object for the speaker. That is one cause with two symptoms: the
# flatness above, and the Kadoman leak that `_check_presence_knowledge_channel`
# exists to catch.
#
# These kinds keep the Director's voice because a full character call would buy
# nothing: their speech is formulaic or barely linguistic -- a beast's snarl, a
# swarm, a drone's stock phrase. Anything PERSON-shaped is routed to the
# background stage, which gives it its own call, its own perception object and
# its own recognition of the room. The list is deliberately narrow: routing a
# borderline speaker costs one call and gets a better line, while keeping one
# costs the defect this whole change exists to remove.


def director_may_voice(speaker, scene, presence_rec=None):
    """Whether the Director may author this background speaker's dialogue.

    Kind is read from the scene entity, then from the presence record's own
    sketch. An UNKNOWN kind routes to the background stage -- the conservative
    direction, because the failure it avoids (a person voiced as filler) is the
    one that was actually measured, and the cost of being wrong is one model
    call rather than a flat line and a possible leak.
    """
    name = str(speaker or "").strip()
    if not name:
        return False
    ents = (scene or {}).get("entities") or {}
    ent = ents.get(name)
    if not isinstance(ent, dict):
        lowered = name.casefold()
        ent = next((v for k, v in ents.items()
                    if isinstance(v, dict)
                    and (str(k).casefold() == lowered
                         or str(v.get("name") or "").casefold() == lowered)), None)
    kind = str((ent or {}).get("kind") or "").strip().casefold()
    if not kind:
        kind = str(((presence_rec or {}).get("sketch") or {}).get("kind")
                   or "").strip().casefold()
    return kind in _ling("_DIRECTOR_VOICEABLE_KINDS")


def _check_presence_knowledge_channel(speaker, quote, sc, presence_rec,
                                      heard_text):
    """Scene-entity references in a Director-voiced presence line that the
    presence has no perceptual channel to.

    The Director is entitled to omniscience -- it owns objective causality --
    and the resolve prompt licenses it to voice unsheeted background
    presences. Nothing sat between those two facts: the voicing was authored
    from the omniscient working state with no perception object for the
    speaker. Chat 65 t2148 is the measured case -- Kadoman, a presence minted
    at turn 9 in eastern_market, referring to "the strange coins and notes"
    shown once at turn 4 in fountain_plaza and pocketed since.

    Deterministic floor, subtractive on purpose: it tests REFERENCES the
    engine can resolve (scene entities by name or alias), never meaning. A
    multi-word phrase matches bare; a single-word alias matches only under a
    definite/possessive determiner, because "the strange coins" claims
    acquaintance while "gold coins" is generic knowledge -- a presence must
    keep every true general thing it can say about its own world (the
    copper-and-silver rule), and a presence with no channel must be free to
    be ignorant in front of the player.

    The channel test is current-scene only (presences are stateless): an
    entity offers a channel when it is placed in the presence's own room and
    not shut inside anything (`hiding_holders_of`, both containment forms).
    An unplaced entity offers no provable channel -- in the measured corpus
    the unplaced entities are precisely the pocketed belongings, while room
    furniture lives in room `anchors`, which this never reads. ``heard_text``
    is what legitimately names things into the presence's beat: everything
    spoken aloud this beat by others, plus the presence's own record and
    characterization. Returns warning strings; empty means no leak.
    """
    q = " %s " % re.sub(r"\s+", " ", str(quote or "")).casefold()
    if not q.strip():
        return []
    entities = (sc or {}).get("entities") or {}
    positions = (sc or {}).get("positions") or {}
    speaker_cf = str(speaker or "").strip().casefold()
    heard_cf = str(heard_text or "").casefold()

    p_room = room_of(sc, speaker)
    if not p_room:
        by_name = {str((e or {}).get("name") or "").strip().casefold(): eid
                   for eid, e in entities.items() if isinstance(e, dict)}
        eid = by_name.get(speaker_cf)
        if eid:
            p_room = positions.get(eid) or room_of(sc, eid)
    if not p_room:
        p_room = ((presence_rec or {}).get("sketch") or {}).get("station_room")

    warnings = []
    for eid, edef in entities.items():
        if not isinstance(edef, dict):
            continue
        name = str(edef.get("name") or "").strip()
        name_cf = name.casefold()
        if name_cf and name_cf == speaker_cf:
            continue  # a presence may always speak of itself
        phrases = {p for p in
                   ({name} | {str(a).strip()
                              for a in (edef.get("aliases") or [])})
                   if p and len(p) >= 3}
        if not phrases:
            continue
        if any(p.casefold() in heard_cf for p in phrases):
            continue  # named aloud in the presence's beat, or its own record
        e_room = (positions.get(eid) or room_of(sc, eid)
                  or (room_of(sc, name) if name else None))
        concealed = bool(hiding_holders_of(sc, eid)) or (
            bool(name) and bool(hiding_holders_of(sc, name)))
        if p_room and e_room == p_room and not concealed:
            continue  # placed here, in the open: a channel exists
        hit = None
        for p in sorted(phrases, key=len, reverse=True):
            pcf = p.casefold()
            if len(p.split()) >= 2:
                if re.search(r"(?<!\w)%s(?!\w)" % re.escape(pcf), q):
                    hit = p
                    break
            elif re.search(
                    r"(?<!\w)(?:%s)\s+(?:[\w'-]+\s+){0,2}%s(?!\w)"
                    # Determiners that make a reference DEFINITE. "That explains the strange
                    # coins" refers to HER coins, a thing in the world; "local trade runs on
                    # copper and silver coins" is knowledge about coins in general. The definite
                    # article is what turns a generality into a claim of acquaintance, so it is
                    # what gates the single-word match below.
                    % ("|".join(_ling("_DEFINITE_DETS")), re.escape(pcf)), q):
                hit = p
                break
        if hit:
            where = "unplaced" if not e_room else e_room
            warnings.append(
                f"Background presence {speaker!r} references {hit!r} "
                f"({name or eid}: {where}"
                + (", concealed" if concealed else "")
                + f") with no perceptual channel from "
                + (repr(p_room) if p_room else "an unknown room")
                + " (presence-knowledge channel)."
            )
    return warnings


def _check_player_interiority_authority(resolved_event, player_name,
                                        declared_text="", other_names=()):
    """Interior states a resolved_event asserts about the PLAYER.

    The mirror of `_check_player_act_authority` for feeling rather than doing,
    and the same boundary. The Director owns objective causality; it does not
    own what is inside the protagonist. It may report every observable the
    body shows -- trembling, wide eyes, a shrill cry -- and must stop there,
    because naming the state behind them decides for the player what their
    character feels.

    Live, alpha 6.3, chat 52 turn 19: the player typed only "W-what did you do
    to me!?" and the resolve wrote "the shrill, PANICKED cry" and "she takes in
    the GENUINE TERROR in those wide eyes". Perception then copied both into
    another character's view, so an invented interior state became something a
    second mind had observed as fact.

    Exempt: anything the player themselves wrote. If they declared the fear,
    it is theirs to declare -- this catches what arrives from nowhere.
    `_INTERIOR_CERTAINTY` is flagged only ALONGSIDE an interior word, because
    "genuine" is unremarkable on its own and damning next to "terror".

    A sentence counts as being about the player when it NAMES them (they may be
    its object -- "she takes in the genuine terror in those wide eyes" is about
    the player from another body's side) or when subject tracking resolves it
    to them. The second was added after chat 56 ("Run!") t6: against a player
    who declared only "You imitate them slightly and shudder", the resolve
    wrote "She looks at him, still shaky, but the terror in her eyes has begun
    to recede" -- deciding the player's emotional arc for them. The name-only
    test could not see a pronoun subject, so nothing fired, and perception
    copied the sentence into the player's OWN view.
    """
    if not resolved_event or not player_name:
        return []
    declared = str(declared_text or "").casefold()
    all_names = [player_name] + [
        n for n in (other_names or []) if n and n != player_name]
    warnings = []
    for body, subject in _sentence_subjects(resolved_event, all_names):
        if not body:
            continue
        low = body.casefold()
        if subject != player_name and not _mentions_player(low, player_name):
            continue
        # Interior states a resolved_event may not assert about the PLAYER. Nouns and
        # adjectives that name what is INSIDE a mind, as against the surface a body
        # shows: "trembling", "wide eyes", "a shrill cry" are observable and always
        # allowed; "terror", "panic", "she realises" are not.
        #
        # Verbs that report a mind's own operation rather than its body's motion.
        #
        # Words that assert an interior state is TRUE, which no observer may know.
        hits = [w for w in _ling("_INTERIOR_STATES")
                if re.search(rf"\b{re.escape(w)}\b", low)
                and not re.search(rf"\b{re.escape(w)}\b", declared)]
        hits += [v for v in _ling("_INTERIOR_VERBS")
                 if re.search(rf"\b{re.escape(v)}(?:s|es|d|ed|ing)?\b", low)
                 and not re.search(rf"\b{re.escape(v)}", declared)]
        if not hits:
            continue
        certainty = [c for c in _ling("_INTERIOR_CERTAINTY")
                     if re.search(rf"\b{re.escape(c)}\b", low)]
        warnings.append(
            "Player interior state not declared this beat "
            "(player-interiority authority): "
            f"{sorted(set(hits))[:3]}"
            + (f" asserted as {certainty[0]!r}" if certainty else "")
            + f": {body[:120]!r}")
    return warnings


def _mentions_player(low_sentence, player_name):
    """Whether a sentence is ABOUT the player -- their name, or a possessive
    reaching for them. Pronouns are not guessed at: "her terror" in a
    two-woman scene could be either of them, and a guess here would flag
    ordinary NPC description."""
    for form in _player_name_forms(player_name):
        if re.search(rf"\b{re.escape(form.casefold())}\b", low_sentence):
            return True
    return False


def _undeclared_world_object(clause, declared_low):
    """The world object a clause has the player take hold of, when the player's
    own declaration never mentions it. None when the clause touches only their
    own body, reaches for nothing, or names something they already declared."""
    # Verbs that put a body in contact with something outside itself.
    # Deliberately excludes verbs that read as manipulation but usually are not:
    # "catch" ("her hair catching the warm light"), "draw" ("draws a breath"),
    # "find" ("finds the words"). The list must earn its flags -- an act guard
    # that fires on scenery is one a maintainer learns to ignore.
    #
    # The player's own body is not a new object. An act on it re-describes what
    # they are doing with themselves, which is elaboration however it is worded --
    # "pushes herself upright" for a declared "slowly stands up".
    #
    # The DIRECT object a verb takes -- the noun it acts ON, with no preposition
    # in between. "grip the edge" is taking hold of the world; "pressed flat
    # AGAINST the cold metal" is a body bracing itself, and reading that as
    # seizing the metal is how a guard starts crying wolf on ordinary prose.
    # The captured group is the whole noun phrase after the article; the HEAD noun
    # is its last word, so "the warm light" reads as "light" rather than "warm".
    for match in re.finditer(cue_boundary_pattern(_ling("_MANIPULATION_VERBS")), clause, re.I):
        obj = _ling("_DIRECT_OBJECT_RE").match(clause[match.end():])
        if not obj:
            continue
        phrase = obj.group(1).split()
        noun = phrase[-1].casefold()
        # A phrase headed by the player's own body is elaboration whatever
        # sits in front of it: "the edge of the console" is the console.
        if noun in _ling("_OWN_BODY_NOUNS") or any(
                w.casefold() in _ling("_OWN_BODY_NOUNS") for w in phrase):
            continue
        if re.search(rf"\b{re.escape(noun)}", declared_low):
            continue
        return noun
    return None


def _claim_authority_kind(claim, player_name):
    """Which grant a claim needs. `None` for a claim no mode restricts.

    `subject_id` alone cannot answer this, and a played beat proved it twice in
    one story. `_extract_authority_claims` resolves an asserted effect to the
    DECLARING ACTOR when the action named no targets -- a deliberate fallback,
    so a player's own body acts (a wave, going rigid) stop tripping the resolve
    seam's 'no resolvable subject' note. But "named no target" is not the same
    fact as "was about my own body": it is equally what a world assertion the
    interpret stage typed as an action looks like.

    Live, the first hard-mode story ever played (2026-08-18, the empty house),
    both on turns where `targets` was empty and the fallback fired:

      * "Two guards come around the corner from the stair" became an ACTION
        rather than the `event` branch that exists for it, so the claim read
        subject_id="Wren", `actor_only` granted it as the player's own body,
        and two guards walked into the world unchallenged.
      * "I take the west door's handle and force the lock; the vault door
        swings open" minted the effect `west door opens, revealing a vault`
        with subject_id="Wren" -- a claim about a DOOR, filed under the
        player's body.

    Reading the prose instead does not save it: the first has no first person
    and the second has plenty, so any test on the wording grants exactly the
    wrong one. What separates them is not in the words at all -- it is that
    the subject was GUESSED. So an inferred subject is not evidence of a body,
    and a mode that exists to withhold authorship may not resolve the doubt in
    the author's favour. It falls to `own_effect`, which `explicit_outcomes`
    and `world_author` still grant; only `actor_only` tightens, which is the
    rung where tightening is the point.

    The cost is stated plainly: under `actor_only` a genuine "I raise my hand"
    is adjudicated rather than true in advance. The declaration still stands
    verbatim, is still resolved, still narrated -- and nothing in the scene
    opposes a raised hand, so it goes up. What it no longer does is bind the
    diff before the Director has read it.
    """
    if str(claim.get("scope") or "") != "effect":
        return None          # a contestable intent is already the Director's
    subject = str(claim.get("subject_id") or "").strip()
    player = str(player_name or "").strip()
    if (player and subject.casefold() == player.casefold()
            and not claim.get("subject_inferred")):
        return "own_body"
    if str(claim.get("claim_id") or "").endswith(":event"):
        return "world"
    return "own_effect"


def apply_player_authority(out, mode, player_name=None):
    """Enforce a `PlayerAuthorityMode` on one interpreted beat, in place.

    The enum has existed since the vocabulary was written and was consumed
    nowhere; this is the consumer. It runs on the interpret output AFTER claim
    extraction, which is the only place both representations of the same
    declaration are on the table at once -- the sequence element the beat is
    resolved from, and the claim the resolve seam holds the diff to. Touching
    one and not the other is how a downgrade becomes invisible: the claim stops
    being non-rejectable while the element still says the effect already
    happened, and the Director reads the element.

    Two things move, and both must:

      * the CLAIM's scope, `effect` -> `intent`, which is what
        `_player_claim_findings` reads to decide a claim may not be rejected;
      * the sequence element's `commitment`, `asserted` -> `contestable`, which
        is what the reaction gate reads to decide whether the character this
        was done to gets to contest it physically. Hard mode without this is
        hard mode the cast cannot participate in.

    Nothing is deleted and nothing is rewritten. A downgraded declaration is
    still the player's words, still resolved, still narrated -- it is merely no
    longer true in advance. Returns the record of what moved, which the caller
    puts in front of the Director and on the step, so a refusal is answerable
    rather than silent.
    """
    # `normalize_player_authority` owns this vocabulary (story/scene.py): it is
    # what `player_authority` runs on the stored mode and on every history
    # entry, and it folds an unreadable value to the DEFAULT. A second copy
    # here -- a bare `str()` and a dict `.get` with the top rung as fallback --
    # answered `world_author` for any spelling the table did not hold
    # literally, so a story tightened to `actor_only` was handed the whole
    # ladder back by a capital letter.
    granted = PLAYER_AUTHORITY_GRANTS[normalize_player_authority(mode)]
    if not isinstance(out, dict):
        return []
    flow = out.get("flow")
    claims = _dict_list(flow.get("authority_claims")) if isinstance(
        flow, dict) else []
    records = []
    downgraded_elements = set()
    for claim in claims:
        kind = _claim_authority_kind(claim, player_name)
        if kind is None or kind in granted:
            continue
        claim["scope"] = "intent"
        records.append({
            "claim_id": claim.get("claim_id"),
            "kind": kind,
            "mode": mode,
            "predicate": str(claim.get("predicate") or ""),
            "source_text": str(claim.get("source_text") or ""),
        })
        # `claim:<index>:...` -- the sequence position the claim came from.
        parts = str(claim.get("claim_id") or "").split(":")
        if len(parts) >= 2 and parts[1].isdigit():
            downgraded_elements.add(int(parts[1]))
    for index, element in enumerate(_dict_list(out.get("sequence"))):
        if index not in downgraded_elements:
            continue
        if element.get("commitment") == "asserted":
            element["commitment"] = "contestable"
    return records


def _check_player_act_authority(resolved_event, declared_actions, player_name,
                                other_names=(), declared_text=""):
    """Physical acts a resolved_event gives the PLAYER that they did not declare
    (live: Elevator Adventure t63 -- the player said only "Let's get going?" and
    the Director had them take a bottle, drink from it and nod; t59 -- the player
    ASKED "I hope you don't mind if I lean on you" and the Director performed the
    leaning for them).

    Adding detail to a declared act is legitimate and is NOT flagged -- the
    Director is supposed to render an act richly. What this catches is an act
    appearing from nowhere, which then replays when the player declares it a
    beat later, so the same moment happens twice and the scene falls out of
    order.

    Two scopes, as for characters (`_check_character_act_authority`) -- but the
    second is drawn differently, because a character's latitude is not the
    player's. The Director may elaborate a character freely and is narrowed
    only on MOVEMENT; the player owns all of their conduct, so the question
    here is not "what kind of act" but "is this act the one they declared".

    * The player declared NO action this beat: any act is invented by
      construction, and the full verb list applies. Unchanged.

    * The player declared actions: rendering those richly is the Director's
      job and stays untouched however it is worded -- "pushes herself upright"
      elaborates a declared "slowly stands up" and shares not one word with it,
      so no vocabulary test can separate the two. What CAN be separated is
      WHAT the act touches. Elaboration re-describes the player's own body;
      fabrication reaches out and takes hold of the world. So this narrows to
      the one addition that is both unambiguous and consequential: the player
      given a grip on a world object their declaration never mentions.

      Live, chat 56 ("Run!") t10: the player typed `"Heh? What are we doing
      what's going on?" You look genuinely confused.` and the resolve wrote
      "her hands coming up to grip the edge of the console, fingers finding a
      lever as if to steady herself". Perception copied it into the player's
      OWN view as "I grip the console edge", the narrator rendered it as fact,
      and the player's very next input was "Which lever?!" -- the fabricated
      act replayed a beat later, which is the exact failure this guard was
      written to stop. The old blanket `if declared_actions: return []` let it
      through, and this player narrated a gesture on every single beat, so the
      guard was disarmed for the entire story.
    """
    if not player_name:
        return []
    declared_low = None
    if declared_actions:
        declared_low = " ".join(
            f"{a.get('attempt', '')} {a.get('observable', '')}"
            for a in declared_actions if isinstance(a, dict)
        ).casefold() + " " + str(declared_text or "").casefold()
    warnings = []
    all_names = [player_name] + [
        n for n in (other_names or []) if n and n != player_name]
    for sentence, subject in _sentence_subjects(resolved_event, all_names):
        if subject != player_name:
            continue
        # Speech attribution ("Hinami says, ...") is not a physical act; the
        # quote itself is guarded separately by the dialogue_log check and by
        # `_check_prose_quote_authority`.
        without_quotes = _ling("_NARRATION_QUOTE_RE").sub(" ", sentence)
        tail = _strip_subject(without_quotes, subject)
        # Per conjunct, not three words from the subject: one subject governs
        # several verbs, and a window measured from the name sees only the
        # first (see `_predicate_heads`).
        for head, clause in _predicate_heads(tail, 3):
            if declared_low is None:
                if not re.search(cue_boundary_pattern(_ling("_PLAYER_ACT_VERBS")), head, re.I):
                    continue
                detail = ""
            else:
                noun = _undeclared_world_object(clause, declared_low)
                if not noun:
                    continue
                detail = f" (undeclared hold on {noun!r})"
            warnings.append(
                "Player act not declared this beat (player-act authority)"
                f"{detail}: {sentence[:120]!r}"
            )
            break
    return warnings


def _check_player_contact_authority(contact_ops, declared_actions, player_name,
                                    standing_ids=(), cast=()):
    """Contacts a resolve gives the PLAYER'S OWN BODY to perform.

    THE SECOND DOOR ON THE SAME RULE. `_check_player_act_authority` holds the
    boundary in `resolved_event`, and holds it well -- but prose is not the
    only channel that can say the player did something. `state_diff.contact_ops`
    stores an ACTOR, and an op naming the player there asserts that the player
    moved a part of their body, whatever the prose says.

    Measured live (chat 95 t40). The player wrote: `"H-how about the full
    thing..." You lie back on the bed. "W-would you like to sit on my face?"`
    -- one declared act, lying back, and an invitation phrased as a question.
    The prose was clean and the guard passed it (`player_act_warnings: null`),
    because the prose correctly has MIRELLE lower herself. The contact channel
    then wrote `Hinami.tongue -> Mirelle.vulva, press, moving`, and it
    committed. An invitation became the player performing, in the same beat.

    THE PLAYER IS THE ACTOR OR THEY ARE NOT, and the ledger already stores
    which. An op where the player is the TARGET is somebody else's conduct --
    a body pressing against theirs, or forcing its way in -- and the engine
    owns all of it; none of that is checked here. What the player does with
    their own tongue, and how their own mouth moves, is theirs.

    Elaboration stays legitimate, exactly as in the prose check, and the test
    is REACH rather than vocabulary: a declared act that reaches this body
    licenses the Director to render what that contact involves, however
    differently worded. Measured against the same run -- t23 declared "slide
    the shoulder straps of Mirelle's chemise" and got `hand -> upper arm`;
    t35 declared "clamp thighs around Mirelle's head" and got `vulva ->
    Mirelle`; t32 declared "run fingers through Mirelle's hair" with an EMPTY
    `targets` list. All three reach Mirelle and all three are correct. t40
    reaches the bed and nothing else.

    Reach is read from both places the pipeline records it, because neither
    is reliable alone: `targets` carries a display name in some beats and a
    cast id in others (t23: `['72']`), and is empty in beats whose attempt
    text names the body outright (t32).

    Returns ``[(index, warning)]`` so the caller can both report and, if a
    retry does not clear it, drop the op -- a body acting without its owner
    is not a soft property.
    """
    if not player_name or not isinstance(contact_ops, list):
        return []
    ids = {str(i) for i in (standing_ids or [])}
    reached, folded_player = set(), str(player_name).strip().casefold()
    by_id = {}
    for entry in (cast or []):
        if not isinstance(entry, dict):
            continue
        sheet = entry.get("sheet")
        name = (character_name_from_text(sheet) if isinstance(sheet, str)
                else character_name(sheet or {}))
        if entry.get("id") is not None and name:
            by_id[str(entry["id"])] = name.strip().casefold()
    for act in (declared_actions or []):
        if not isinstance(act, dict):
            continue
        for target in (act.get("targets") or []):
            token = str(target).strip()
            reached.add(by_id.get(token, token.casefold()))
        text = " ".join(str(act.get(k) or "") for k in
                        ("attempt", "observable", "verb")).casefold()
        for name in by_id.values():
            # ANY PART OF THE NAME REACHES THE BODY. Declarations use the
            # spelling a person would -- t32's "run fingers through Mirelle's
            # hair" names her as surely as the full "Mirelle Sulmirath" does,
            # and requiring the whole string read that beat as reaching nobody.
            if name and (name in text or any(
                    len(part) >= 4 and part in text for part in name.split())):
                reached.add(name)
    out = []
    for index, op in enumerate(contact_ops):
        if not isinstance(op, dict):
            continue
        if str(op.get("op") or "add").strip().casefold() not in ("add", "change"):
            continue
        if str(op.get("actor") or "").strip().casefold() != folded_player:
            continue
        target = str(op.get("target") or "").strip()
        if not target or target.casefold() == folded_player:
            continue
        # BODIES ONLY. This is the rule about one person's conduct on another,
        # and a bed is not a person: lying back on it, or a back arching
        # against it, is posture the world resolves. Restricting the check to
        # registered bodies is also what keeps it from firing on the furniture
        # every reclining beat carries (chat 95 t30, t40).
        if target.casefold() not in set(by_id.values()):
            continue
        if target.casefold() in reached:
            continue
        # A standing hold re-stated is not a new act; only a contact this beat
        # INVENTS is one.
        if str(op.get("contact_id") or "") in ids:
            continue
        out.append((index, (
            "Player contact not declared this beat (player-act authority): "
            "%s's %s -> %s's %s. The player declared nothing reaching %s."
            % (player_name, op.get("actor_part") or "body", target,
               op.get("target_part") or "body", target))))
    return out


def _cap_repeated_quotes(prose, view, exclude_bodies=()):
    """Cap each spoken line's occurrences in the prose at how many times it
    actually appears in the authoritative source (the view). (Fable A1 / backlog
    P3.) `_dedupe_view_sentences` deliberately exempts quotes so an intentional
    repeat survives, which let a line the narrator both SUMMARIZED and quoted
    verbatim render twice (impostor t9: the last-stand speech; t5: Lady Thorne's
    kitchen-door line, verbatim, twice). A quote appearing more often than the
    source authorized is an artifact; drop the surplus occurrences, keep the
    first. The player's own lines are handled by the echo strip and excluded.
    """
    if not prose:
        return prose
    excluded = {re.sub(r"\s+", " ", str(b).casefold()) for b in (exclude_bodies or [])}
    quote_re = _ling("_QUOTE_SPAN_RE")
    source_text = re.sub(r"\s+", " ", str(view or "").casefold())
    # Source count per body: how many times the view presents that exact line.
    source_counts = {}
    for m in quote_re.finditer(str(view or "")):
        body = re.sub(r"\s+", " ", m.group(2).strip().casefold())
        if body:
            source_counts[body] = source_counts.get(body, 0) + 1

    seen = {}
    out_parts = []
    last = 0
    for m in quote_re.finditer(prose):
        body = re.sub(r"\s+", " ", m.group(2).strip().casefold())
        if not body or body in excluded:
            continue
        cap = source_counts.get(body, 1)
        seen[body] = seen.get(body, 0) + 1
        if seen[body] > cap:
            # Surplus occurrence: excise this quoted span (keep the text
            # around it; the dangling-verb heal below tidies "he says ,").
            out_parts.append(prose[last:m.start()])
            last = m.end()
    if not out_parts:
        return prose
    out_parts.append(prose[last:])
    result = "".join(out_parts)
    result = _dangling_speech("verb").sub(_heal_dangling_verb, result)
    result = _dangling_speech("colon").sub(_heal_dangling_colon, result)
    result = _collapse_empty_quote_debris(result)
    return re.sub(r"\s{2,}", " ", result).strip()


def _quote_body(quote):
    return (quote or "").strip().strip('"' + "'" + "\u201c\u201d\u2018\u2019")

# What survives muffling: stressed, longer words. Function words are the first
# thing lost, which is why an overheard fragment is a scatter of nouns and verbs
# rather than a summary.
_MUFFLE_KEEP_MIN = 4
_MUFFLE_MAX_WORDS = 3


#: Content-bearing runs in a script that does not space its words: kanji,
#: katakana, Hangul, and any Latin/digit run carried through code-switching.
#: Hiragana is deliberately absent -- it carries particles and inflection,
#: which is precisely the low-information half that drops out of a half-heard
#: line, and dropping it leaves chunks that are still verbatim substrings.
_UNSPACED_CONTENT_RUN = re.compile(
    r"[㐀-䶿一-鿿豈-﫿]+|[ァ-ヿ]+|[가-힯]+|[A-Za-z0-9]+")


def _muffle_tokens(body):
    """Verbatim chunks of a line, and the shortest one worth keeping.

    Returns `(tokens, keep_min)` because the threshold is a property of the
    script, not a constant: four characters is a short English word and a
    whole Japanese clause.

    `.split()` alone made this a no-op wherever words are not space-separated
    -- the entire utterance came back as one "word", sailed past the
    `_MUFFLE_MAX_WORDS` filter, and a character who should half-hear a
    whispered secret heard all of it. Every chunk here is still a verbatim
    substring, which `_scrub_invented_dialogue` depends on.
    """
    text = str(body or "")
    if _UNSPACED_SCRIPT.search(text):
        return _UNSPACED_CONTENT_RUN.findall(text), 1
    return ([w.strip(".,;:!?\"'“”‘’") for w in text.split()],
            _MUFFLE_KEEP_MIN)


def _muffle_middle(body, keep=3):
    """The middle few content chunks of a line, for the interaction loop.

    Shares `_muffle_tokens` with `_muffled_fragment` so there is ONE rule for
    what survives half-hearing. The loop used to slice `quote.split()`, which
    yields a single token in a language without spaces and therefore returned
    the whole utterance.

    And the pack's `muffle_join` for how the survivors are SET OUT, which was
    the other half of that same argument: a hardcoded ASCII space put 「小瓶
    捨」 in a story whose every other muffled line reads 「……小瓶……捨……」.
    A separator belongs to the language -- Japanese sets an ellipsis as the
    doubled leader with no spaces, and a half-width gap between two kanji runs
    reads as broken typesetting rather than as a gap in hearing. The template
    around this fragment supplies the leading and trailing ellipsis, so only
    the join is read here.
    """
    tokens, keep_min = _muffle_tokens(body)
    kept = [w for w in tokens if len(w) >= keep_min]
    if not kept:
        return _text("muffled_indistinct")
    start = max(0, len(kept) // 2)
    join = str(compositor_value("muffle_join"))
    return join.join(kept[start:start + keep])


def _muffled_fragment(body):
    """A partial transcript of what actually carried, not a description of it.

    This used to render "...something about <three middle words>...", which
    narrates the ACT of half-hearing instead of delivering the percept: the view
    said the perceiver heard something about a thing rather than letting them
    hear the pieces. It also read badly in prose and gave the narrator a stock
    phrase to echo.

    Each surviving word is emitted as its own ellipsis-separated chunk, and only
    ever verbatim -- `_scrub_invented_dialogue` validates a muffled line by
    checking every chunk against the lines actually spoken, so a chunk stitched
    across punctuation ("ledger, sink" -> "ledger sink") would fail that
    check and get the whole line dropped.
    """
    words, keep_min = _muffle_tokens(body)
    kept = [w for w in words if len(w) >= keep_min]
    if not kept:
        return _text("muffled_indistinct")
    if len(kept) > _MUFFLE_MAX_WORDS:
        # The longest carry best; original order is preserved so the fragment
        # still tracks the shape of the sentence.
        strongest = set(sorted(kept, key=len, reverse=True)[:_MUFFLE_MAX_WORDS])
        seen, kept2 = set(), []
        for w in kept:
            if w in strongest and w not in seen:
                seen.add(w)
                kept2.append(w)
        kept = kept2
    # The glyphs belong to the language: Japanese sets an ellipsis as the
    # doubled three-dot leader with no spaces (……棚……小瓶……), and ASCII dots
    # with half-width gaps read as broken typography inside Japanese prose.
    # The pack's own `muffled_indistinct` already used the right form, so the
    # same feature was being typeset two different ways.
    lead = str(compositor_value("muffle_ellipsis"))
    join = str(compositor_value("muffle_join"))
    return lead + join.join(kept) + lead


# `tone` is a free-text field and models fill it with two grammatically
# different things: an abstract NOUN ("warmth", "urgency", "a hint of
# steel") and an ADJECTIVE or adjective phrase ("bright", "quietly
# authoritative"). One slot was built for the first and fed both, so every
# adjectival tone rendered as "says with quietly authoritative in their
# voice" -- constant, reader-facing, and flagged in the corpus replay's
# prose sample as one of the two things a reader notices within minutes.
#
# The head word decides, and the DEFAULT IS ADJECTIVE: adjectives are what
# models emit most, and they are the half that was broken. A noun wrongly
# read as an adjective gives "in a warmth voice" -- bad, so the noun list
# below is explicit about the irregulars that no suffix catches, and the
# suffixes cover the productive endings that cannot be adjectives.


def _tone_clause(tone):
    """The dialogue tag's manner slot, agreeing with what kind of word the
    tone actually is. Returns "" or a leading-space clause."""
    tone = str(tone or "").strip().rstrip(".,;:")
    if not tone:
        return ""
    # An observable BEHAVIOUR, not a vocal quality: "with a smirk".
    articles = tuple(compositor_value("articles"))
    article_re = r"^(?:" + "|".join(map(re.escape, articles)) + r")\b"
    behavior_re = r"\b(?:" + "|".join(map(
        re.escape, compositor_value("tone_behavior_words"))) + r")\b"
    if re.search(behavior_re, tone, re.I):
        indefinite = compositor_value("indefinite_article")
        article = "" if re.match(article_re, tone, re.I) \
            else indefinite["other"] + " "
        return _text("tone_behavior", article=article, tone=tone)
    head = [w for w in re.split(r"[^\w]+", tone) if w]
    head = head[-1].casefold() if head else ""
    if head in _ling("_TONE_NOUNS") or head.endswith(_ling("_TONE_NOUN_SUFFIXES")):
        return _text("tone_noun", tone=tone)
    if re.match(article_re, tone, re.I):
        return _text("tone_article", tone=tone)
    indefinite = compositor_value("indefinite_article")
    article = (indefinite["vowel"] if tone[:1].casefold()
               in indefinite["vowels"] else indefinite["other"])
    return _text("tone_adjective", article=article, tone=tone)


def _inject_dialogue(view, display, quote, level, volume, can_see,
                    conducted=False, tone="", articulation=""):
    if level == "none":
        return view
    body = _quote_body(quote)
    if not body or _contains_quote(view, body):
        return view
    if level == "fragment":
        return _append_once(
            view, _text("muffled", fragment=_muffled_fragment(body)))
    if conducted:
        # Heard from inside the speaker: the mass around the listener is the
        # medium, so it arrives low and close rather than across a distance.
        return _append_once(
            view,
            _text("dialogue_conducted", label=display, body=body))
    # Two forms of the same verb, because the two frames below take different
    # ones. "You hear X" is a bare-infinitive construction -- "you hear her
    # SAY", never "you hear her says" -- and this wrote the inflected form into
    # both, so every view of a speaker the perceiver could not see carried
    # broken English: 226 occurrences across 71 turns of the live corpus, all
    # of them in exactly the situations this engine cares most about (a voice
    # through a door, in the dark, from inside an enclosure).
    verbs = compositor_value("dialogue_verbs")
    verb, bare = verbs.get(volume, verbs["default"])
    # Articulation is FORMATION, stamped at the source (see
    # _stamp_dialogue_articulation): the same malformed sound reaches every
    # listener, so it renders identically for all of them and rides the
    # dialogue tag rather than gating the level. The quote itself stays
    # verbatim -- the fidelity scrubs match on it, and dialogue fidelity
    # forbids rewriting words actually said.
    articulation_text = compositor_value("articulation")
    artic = articulation_text.get(articulation, articulation_text["default"])
    manner = _tone_clause(tone) if can_see else ""
    if can_see:
        add = _text("dialogue_visible", label=display, verb=verb,
                    manner=manner, articulation=artic, body=body)
    else:
        add = _text("dialogue_unseen", label=display, verb=bare,
                    articulation=artic, body=body)
    return _append_once(view, add)


def _content_tokens(text):
    """Distinctive (stopword-stripped, crudely stemmed) word tokens of a phrase
    -- the basis for 'has this beat already been narrated?' overlap."""
    toks = []
    for raw in re.split(r"[^\w]+", str(text or "").lower()):
        if not raw or raw in _ling("_OBSERVED_STOPWORDS"):
            continue
        for suf in ("ing", "ed", "es", "s"):
            if len(raw) > len(suf) + 2 and raw.endswith(suf):
                raw = raw[:-len(suf)]
                break
        toks.append(raw)
    return toks


def self_name_forms(primary_name, forms=None):
    """Every textual handle that means THIS perceiver, for _self_second_person.

    The scene keys alone are not enough: they carry the full display name and
    authored aliases, and prose does not. Measured live, a Director clause
    said "the base of Elyra's shaft" inside Elyra Voss's own view, and her
    forms -- 'Elyra Voss', 'elyra_voss_imp', 'Madame Elyra', ... -- matched
    none of it, so her own view named her in the third person on fifteen
    turns of one story. Prose reaches for the FIRST name of a multi-word
    name, so the word tokens of the primary name are forms too --
    `_player_name_forms` already draws exactly this conclusion for the
    player, which is why only the CHARACTERS' views carried the defect.

    Tokens come from the primary name only, never from aliases: an alias like
    'The Succu-Masseuse' would contribute 'The'. An ordinary-word token is
    safe to include because _self_second_person already matches those
    case-sensitively (_COMMON_WORD_NAMES).
    """
    out, seen = [], set()
    for form in [*(forms or []), *_player_name_forms(primary_name)]:
        text = str(form or "").strip()
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            out.append(text)
    return out


# Head nouns too generic to shorten a minted label onto. "the person"/"the
# figure" is not a shortening of one body's descriptor, it is the word every
# stranger label is built from, and rewriting it into "you" would claim any
# passing body as the perceiver.


def self_reference_forms(name, appearance=None, aliases=None, *,
                         labels=(), avoid=()):
    """The EPITHETS this engine mints for one body, as self-reference forms.

    `self_name_forms` above answers "what does prose call this mind by NAME".
    This answers the other half, and it exists because a name is not the only
    handle the engine itself puts into circulation: `_unknown_actor_label`
    mints a descriptor for every body an observer has not recognized, and
    every mind that receives that descriptor then writes it back out in its
    own declarations. The Director does it too.

    Measured live (three-model playthrough, 2026-08-12): the persona Corin
    reads "A young smith's apprentice with a borrowed sword", the composer
    minted "the young smith's apprentice" for every character in the square,
    and it came back through `director_resolve` ("Bryn turns toward the young
    smith's apprentice") and through the cast's own observable surfaces ("eyes
    settling on the sword at the apprentice's hip") into Corin's OWN view.
    The composer translates a canonical NAME into "you" for the body it
    belongs to; handed the epithet it minted, it had nothing to translate, so
    the player read about himself in the third person, described by a label
    that exists only because other people do not know who he is.

    The forms returned are deliberately narrow:

    - the exact minted label(s) -- the base `_unknown_actor_label` descriptor
      plus whatever `labels` the caller actually minted this beat (a widened
      or ordinal-distinguished variant), because those are the strings the
      engine put into circulation and nothing else is;
    - one SHORT definite form ("the apprentice") cut from a label's head
      noun, because prose shortens a long descriptor on second mention and
      that is exactly how the live case reached the player. Guarded three
      ways: the label must be long enough for the short form to be a genuine
      shortening, the head noun must not be generic
      (`_GENERIC_LABEL_HEADS`), and the head noun must not appear in any
      `avoid` label.

    `avoid` is the set of labels this observer currently holds for OTHER
    bodies. Any form colliding with one of them is dropped outright: two
    strangers who look alike can share a descriptor, and rewriting a
    reference to one of them into "you" would tell the perceiver they did
    something somebody else did. Under-matching costs one clumsy sentence;
    over-matching invents an act.

    Indefinite variants ("a young smith's apprentice") are NOT returned. That
    phrasing is how prose introduces a body nobody has met, so matching it
    would reach for referents this cannot check.
    """
    avoid_labels = {str(a or "").strip().casefold()
                    for a in (avoid or []) if str(a or "").strip()}
    avoid_words = set()
    for label in avoid_labels:
        avoid_words.update(re.findall(r"[\w']+", label))
    minted = []
    for label in [_unknown_actor_label(name, appearance, aliases), *(labels or [])]:
        label = str(label or "").strip()
        if not label or label.casefold() in avoid_labels:
            continue
        if label.casefold() not in {m.casefold() for m in minted}:
            minted.append(label)
    out = list(minted)
    for label in minted:
        words = re.findall(r"[\w']+", label)
        if len(words) < 3:
            continue
        head = words[-1].casefold()
        if head in _ling("_GENERIC_LABEL_HEADS") or head in avoid_words or len(head) < 3:
            continue
        short = f"the {words[-1]}"
        if short.casefold() in avoid_labels:
            continue
        if short.casefold() not in {m.casefold() for m in out}:
            out.append(short)
    return out


def _self_second_person(text, forms):
    """Rewrite a PERCEIVER's own name/alias forms inside engine-supplied prose
    into second person, before that prose is injected into their own view.

    Every perception view is written from its perceiver's own vantage ("You
    are in the lobby..."), but the deterministic action backstop appends an
    actor's `observable` surface verbatim -- and those surfaces are authored
    in third person by the acting agent, naming everyone else by name. So
    Dr. Moon's "steps briskly from the barricade toward Hinami" landed in
    HINAMI'S OWN view, producing the same beat twice in two different persons
    ("...beside your shoulder. Dr. Moon steps briskly ... toward Hinami...")
    and handing the narrator a player_view that names the player in the third
    person -- the exact thing its PERSON DISCIPLINE rule forbids.

    Scope is deliberately narrow and deterministic: only the perceiver's own
    explicit name/alias tokens are rewritten (possessive -> "your", every
    other form -> "you"), never pronouns. A third-person pronoun later in the
    same clause that referred to the perceiver ("...beside her shoulder") is
    left alone -- resolving that anaphora needs a referent the engine cannot
    determine when the actor shares the perceiver's pronouns, and a wrong
    guess would be worse than a mildly loose one. Quoted spans survive
    verbatim: a name spoken aloud is sensory signal, and dialogue fidelity
    forbids rewriting it.
    """
    text = str(text or "")
    if not text:
        return text
    patterns = []
    for form in forms or []:
        form = str(form or "").strip()
        if not form:
            continue
        # Ordinary-English single-token names ("Rose", "Hope") are matched
        # case-sensitively, exactly as the identity scrub does, so common
        # lowercase prose is never rewritten into second person.
        flags = 0 if form.casefold() in _ling("_COMMON_WORD_NAMES") else re.I
        patterns.append(re.compile(
            r"(?<!\w)" + re.escape(form) + r"(['’]s)?(?!\w)", flags))
    if not patterns:
        return text
    segments = _ling("_QUOTED_SPAN_RE").split(text)
    for i in range(0, len(segments), 2):  # even indices = unquoted prose
        before = segments[i]
        after = before
        for pattern in patterns:
            after = pattern.sub(_self_pronoun_sub, after)
        # A name in SUBJECT position leaves the verb inflected for third
        # person singular ("Hinami is caught" -> "You is caught"), which
        # would reach the player as visibly broken prose. Only run the
        # repair on segments this pass actually rewrote.
        segments[i] = _fix_you_agreement(after) if after != before else before
    return "".join(segments)


def _base_from_third_person_s(word):
    """Undo third-person-singular -s/-es/-ies on a regular present verb, or
    return None when the word is not one."""
    low = word.lower()
    if (low in _ling("_NON_VERB_S_WORDS") or len(low) <= 3 or not low.endswith("s")
            or low.endswith(("ss", "us", "is", "as", "'s", "’s"))):
        return None
    if low.endswith("ies") and len(low) > 4:      # carries -> carry
        return word[:-3] + "y"
    if low.endswith("es") and low[:-2].endswith(_ling("_ES_STEM_ENDINGS")):
        return word[:-2]                          # catches -> catch
    return word[:-1]                              # steps -> step


def _fix_you_agreement(text):
    """Re-inflect the verb after a "you" that replaced a third-person subject.

    Handles the irregular copulas/auxiliaries by table and regular present-
    tense verbs by undoing the third-person-singular -s. "you is/was/has/does
    <x>" and "you <verb>s" are never grammatical English, so this is safe to
    run over prose that already contained a legitimate "you".
    """
    def _sub(m):
        you, gap, word = m.group(1), m.group(2), m.group(3)
        # Third-person-singular forms that must agree with an inserted "you".
        #
        # Words that can follow a subject, end in -s, and are NOT verbs -- the guard
        # on the regular-verb rule below, which otherwise strips a meaningful "s"
        # ("You always" -> "You alway"). Deliberately a closed list: a missed entry
        # costs one dropped letter, while dropping the rule entirely costs "You steps".
        #
        #
        # Stems that take -es rather than a bare -s ("catch/catches", "push/pushes",
        # "fix/fixes", "go/goes", "pass/passes"); everything else drops a single -s.
        # "ss" not "s": a stem ending in ONE s is rare ("bus"), while "loses",
        # "raises", "closes" are common and keep their stem-final e.
        fixed = _ling("_YOU_AGREEMENT").get(word.lower())
        if fixed is None:
            fixed = _base_from_third_person_s(word)
        if fixed is None:
            return m.group(0)
        if word[:1].isupper():
            fixed = fixed[:1].upper() + fixed[1:]
        return f"{you}{gap}{fixed}"

    return _ling("_YOU_VERB_RE").sub(_sub, str(text or ""))


def _self_pronoun_sub(m):
    """Replacement callback for _self_second_person: possessive -> your,
    anything else -> you, capitalized when it opens a sentence."""
    word = "your" if m.group(1) else "you"
    before = m.string[:m.start()].rstrip()
    if not before or before[-1] in ".!?\n":
        word = word.capitalize()
    return word


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
                     or words[0].casefold()
                     in _ling("_LEADING_SUBJECT_PRONOUNS")):
        words = words[1:]
    stripped = " ".join(words).strip()
    if not stripped:
        return _text("observable_empty", label=display)
    first = stripped.split(maxsplit=1)[0]
    # Independent subject clause (starts with a capitalized non-actor word that
    # isn't a normal sentence-initial cap): render as its own sentence.
    independent = first[:1].isupper() and first.casefold() not in disp_tokens
    if independent:
        return stripped if stripped.endswith((".", "!", "?")) else stripped + "."
    body = stripped[0].lower() + stripped[1:]
    return _text("observable", label=display, body=body)


def _action_already_rendered(view, display, surface):
    """True when the view already narrates this action (so the deterministic
    backstop should stay silent). Upgrades the old exact-substring test to
    content-token overlap, which catches the LLM's paraphrase of the same
    beat. Biases toward silence: since alpha3.1.2 duplication is the common,
    player-visible failure and a missed injection the rare one."""
    surf = set(_content_tokens(surface))
    if not surf:
        return False
    view_text = str(view or "")
    disp_tokens = _identity_token_set(display)
    for sent in re.split(r"(?<=[.!?])\s+", view_text):
        raw = set(re.split(r"[^\w]+", sent.lower()))
        stoks = set(_content_tokens(sent))
        overlap = surf & stoks
        if not overlap:
            continue
        if len(overlap) / len(surf) >= 0.6:
            return True
        if (disp_tokens & raw) and len(overlap) >= 2:
            return True
    # WHOLE-VIEW pass. The per-sentence loop above misses two common shapes:
    # the perception LLM spreads ONE beat over several sentences ("Dr. Moon is
    # right in front of you, having crossed quickly. Her arm is under yours,
    # bracing you against the wall."), and the sentence splitter itself breaks
    # on the abbreviation in a name like "Dr. Moon" -- which strands the actor
    # token in one fragment and the action tokens in the next, disarming the
    # disp_tokens rule exactly where it was needed. Live consequence (chat 27
    # turn 54): the beat was appended a SECOND time at the end of the view,
    # AFTER the dialogue, so the narrator rendered Dr. Moon crossing to brace
    # the player, then speaking, then crossing to brace them again.
    #
    # Requires the view to NAME this actor and to share strictly more
    # distinctive tokens than the per-sentence rule asks for: the whole view
    # is a far larger surface for coincidental matches than one sentence.
    raw_all = set(re.split(r"[^\w]+", view_text.lower()))
    whole_overlap = surf & set(_content_tokens(view_text))
    if (disp_tokens & raw_all) and len(whole_overlap) >= 3:
        return True
    return False


def _inject_action(view, display, attempt, can_see, event_id=None, delivered=None,
                   self_forms=None):
    """Append one actor's observable action to a perceiver's view.

    `self_forms` are the RECEIVING perceiver's own name/alias forms. They are
    rewritten to second person BEFORE the duplicate check, so the check scores
    the same person the LLM's own prose used ("...beside your shoulder") rather
    than the acting agent's third-person surface -- which is why the duplicate
    slipped through as well as the person mismatch. See _self_second_person.
    """
    if not attempt or not can_see:
        return view
    if delivered is not None and event_id:
        if event_id in delivered:
            return view
        delivered.add(event_id)
    if self_forms:
        attempt = _self_second_person(attempt, self_forms)
    if _action_already_rendered(view, display, attempt):
        return view
    sentence = _observable_predicate(display, attempt)
    if not sentence:
        return view
    return _append_once(view, sentence, marker=sentence)

# `appearance_of` builds a STRUCTURED summary for payload fields -- labelled
# segments joined by semicolons -- which is right for a field a model reads and
# wrong for prose. It was being pasted verbatim into perception views, so every
# view of every turn in a 47-turn chat read:
#
#     "You see A tall figure in a grey travelling coat, hood raised.;
#      clothing state: soaked through, ..."
#
# -- a capital mid-sentence, a full stop before a semicolon, and the field
# labels themselves narrated. Normalizing at the PASTE POINT rather than at the
# five construction sites keeps one mechanism and leaves the payload form,
# which is correct, alone.


def _appearance_as_prose(appearance):
    """A structured appearance summary rendered as something a view can hold."""
    text = str(appearance or "").strip()
    if not text:
        return ""
    for label, replacement in _ling("_APPEARANCE_LABELS"):
        text = text.replace(label, replacement)
    # The base appearance is authored as its own sentence; its terminal stop
    # and leading capital both fight the clause it is now part of.
    text = re.sub(r"\.\s*(?=,)", "", text)
    text = text.rstrip(" .")
    if text[:1].isupper() and re.match(r"^(a|an|the)\b", text, re.I):
        text = text[:1].lower() + text[1:]
    return re.sub(r"\s{2,}", " ", text).strip(" ,")


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

    for pattern in _ling("_VISUAL_CONTRADICTION_RES"):
        text = pattern.sub("", text)

    text = re.sub(r"\s{2,}", " ", text).strip()

    if appearance:
        prose = _appearance_as_prose(appearance)
        # The perception model may already have rendered the same visible
        # body in natural prose. Exact-marker dedupe cannot recognize a
        # paraphrase, which produced a second mechanical "You see ..." tail
        # on the live chat-38 view. Use the same conservative content-overlap
        # test as action injection before adding the deterministic floor.
        if prose and _action_already_rendered(text, display, prose):
            return text
        return _append_once(
            text,
            _text("appearance", description=prose),
            # Marker stays the RAW form: it is what a previous injection would
            # have left behind, and dedupe must catch those too.
            marker=prose or appearance,
        )

    return _append_once(
        text,
        _text("appearance", description=display),
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
    residue = compositor_value("residue")
    lead = residue["lead"].get(level, residue["lead"]["default"])
    frag = []
    if pain:
        frag.append(residue["pain"])
    if targeted:
        frag.append(residue["targeted"])
    if loud_event:
        frag.append(residue["loud_event"])
    if not frag:
        closing = residue["closing"].get(
            level, residue["closing"]["default"])
        return (lead + closing).strip()
    body = residue["separator"].join(frag[:2])
    body = body[0].upper() + body[1:]
    return _text("residue_content", lead=lead, body=body)


def _ensure_environment(view, perceiver, display, rel, vis, action_desc):
    if view:
        return view
    parts = [_text("room", room=perceiver.get("room_name"))]
    if perceiver.get("room_notes"):
        parts.append(perceiver["room_notes"])
    # `same_room` is true for a body sealed inside something standing in the
    # room -- a carried body's position derives to its carrier's. Announcing
    # it as "here with you" and pasting its observable is the same bypass the
    # injection sites had; `concealed` is absent (falsy) for every rel that
    # never went through containment, so open scenes are unchanged.
    if rel.get("same_room") and not rel.get("concealed"):
        parts.append(_text("environment_here", label=display))
        if action_desc:
            # action_desc is now an intent-free `observable` surface (predicate
            # or independent clause); compose it cleanly rather than gluing it
            # after "attempts to" (which double-verbs "attempts to tilts...").
            sentence = _observable_predicate(display, action_desc)
            if sentence:
                parts.append(sentence)
    elif vis:
        parts.append(_text("environment_nearby", label=display))
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
            parts.append(_text("room", room=rname))
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
                parts.append(_text(
                    "fallback_speech", label=speaker,
                    quote=d["exact_quote"]))
        views[pid] = " ".join(parts) if parts else None
    return views

# A speech verb left dangling by the echo strip ("you say.", "I ask,") is healed
# to "<verb> it." The lookahead is SENTENCE-end only ([.!?] or end of string):
# a verb followed by a comma that CONTINUES the sentence ("he says, quiet and
# gentle, 'Ellie'") is a normal attribution around a quote that survived, not a
# dangling verb -- healing it produced "he says it., quiet and gentle," in live
# NPC dialogue whenever the same beat also stripped a player echo (v4).


# ONE vocabulary, shared with the colon healer below -- by construction, not by
# discipline. Two independent literals drifted twice: the colon healer knew
# `add`, `speak`, `voice`, `continue` and `offer` and the verb healer did not,
# so a quote stripped after "as you add," left the fragment "You let the wry
# amusement show as you add," standing on the page with nothing after it (live,
# chat 72); and later the verb healer alone gained `call` and `shout`. Both now
# read `_SPEECH_CUE` through `_dangling_speech` (defined at the top of this
# file), so a pack states what counts as speech ONCE and neither healer can
# hold a vocabulary the other does not.


def _heal_dangling_verb(match):
    """Give a stranded speech verb its object back, in the shape it landed in.

    `it` is deliberately vague: the line itself is what the player already
    knows and what this function exists to keep off the page, so the
    replacement must refer to the utterance without reproducing it.
    """
    heal = _ling("_DANGLING_SPEECH")
    verb = match.group(1)
    if match.group("cont"):
        # A capital straight after the comma means the cut left two sentences
        # welded by it ("I say,  He tells Karen the truth"), so close the
        # first rather than running them together with an object between.
        rest = match.string[match.end():].lstrip()
        if rest[:1].isupper():
            return heal["heal_stop"].format(verb=verb)
        # attribution mid-sentence: keep going
        return heal["heal_cont"].format(verb=verb)
    if match.group("end"):
        # consume the punctuation the wound left; never double it
        return heal["heal_end"].format(verb=verb, end=match.group("end"))
    return heal["heal_stop"].format(verb=verb)   # end of paragraph or prose


# `, ,` and `,,` left where a quote sat between an attribution and its
# continuation. The empty-quote collapser handles the quote marks; nothing
# handled the punctuation on either side of them.
_DOUBLED_COMMA_RE = re.compile(r",(?:[^\S\n]*,)+")

# A quote can also be introduced by an attributive CLAUSE ending in a colon
# ("...and when I speak again it's quieter, almost gentle:"). Stripping the
# player's echoed quote leaves the colon dangling against the next sentence
# (live: v3 t7 "...almost gentle: Vorne swallows once..."). Drop the orphaned
# lead-in back to the preceding clause/sentence boundary -- but only a clause
# that actually carries a speech cue, so a legitimate non-speech colon (a
# list, a ratio, a time) is never eaten. The colon match also consumes an
# orphaned period the strip may have left ("gentle: .").
# The lead-in TEXT is kept -- only the dangling colon (and any orphaned period
# the strip left) is converted to a full stop, so nothing legitimate can be
# eaten. Requiring a speech cue in the same clause keeps this off a real
# non-speech colon (a list, a ratio, a time). `[^.!?:]*` cannot cross a
# sentence boundary, so the cue and the colon are always in one clause.


def _heal_dangling_colon(m):
    return _ling("_DANGLING_SPEECH")["heal_colon"].format(lead=m.group(1))

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
    for match in _ling("_VIEW_QUOTE_BODY_RE").finditer(str(view or "")):
        body = _quote_body(match.group(1))
        if not body:
            continue
        if re.sub(r"\s+", " ", body.casefold()) in excluded:
            continue
        quotes.append(body)
    return quotes

# Punctuation and case are not variation. `_strip_player_echo` matched the
# player's declared line as a literal substring, and a narrator that lightly
# TIDIES what the player typed defeats that completely: declared
# `Anyways your plan doctor?` was rendered `"Anyways, your plan, Doctor?"` --
# two inserted commas and a capitalised Doctor -- and sailed through the guard
# into the page as an unattributed quote (chat 72, turn 35). Correcting the
# player's grammar is the one thing a narrator reliably does, so the guard's
# failure rate was proportional to how well the narrator wrote.
_ECHO_FOLD_RE = re.compile(r"[^\w\s]+")


def _echo_fold(text):
    """One spoken line, folded so only its WORDS remain."""
    return " ".join(_ECHO_FOLD_RE.sub(" ", str(text or "")).casefold().split())


# Below this, a folded match is not evidence of an echo -- "no", "wait", "why"
# recur in anyone's mouth, and the literal pass above already handles a short
# line that arrived unedited.
_ECHO_FOLD_MIN_WORDS = 3


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
        forms = [o + body + c for o, c in _ling("_QUOTE_PAIRS")]
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
        quoted_forms = tuple(o + body + c for o, c in _ling("_QUOTE_PAIRS"))
        matched = any(q in prose for q in quoted_forms)
        if len(body) >= 8 and body in prose:
            matched = True
        if not matched:
            # The narrator tidied it. Fall back to a WORDS-ONLY comparison
            # against each quoted span still in reach -- NPC quotes were
            # masked out above, so anything left is fair game -- and drop the
            # span whose words are the player's, whatever punctuation and
            # capitalisation the narrator gave them.
            folded = _echo_fold(body)
            if len(folded.split()) < _ECHO_FOLD_MIN_WORDS:
                continue
            hit = next((m for m in _ling("_QUOTE_SPAN_RE").finditer(prose)
                        if _echo_fold(m.group(2)) == folded), None)
            if hit is None:
                continue
            prose = prose[:hit.start()] + prose[hit.end():]
            prose = _dangling_speech("verb").sub(
                _heal_dangling_verb, prose)
            prose = _dangling_speech("colon").sub(_heal_dangling_colon, prose)
            continue
        for quoted in quoted_forms:
            prose = prose.replace(quoted, "")
        if len(body) >= 8:
            prose = prose.replace(body, "")
        # Stripping the quote can leave a dangling speech verb ("you say,",
        # "I ask,", "Alex says.") with nothing after it -- the subject varies
        # with narration_person (first/second/third), so match on the verb
        # rather than assuming "you".
        prose = _dangling_speech("verb").sub(_heal_dangling_verb, prose)
        prose = _dangling_speech("colon").sub(_heal_dangling_colon, prose)
    for token, form in masks:
        prose = prose.replace(token, form)
    prose = _collapse_empty_quote_debris(prose)
    # HORIZONTAL WHITESPACE ONLY. This was `\s{2,}` -> " ", which cleans the
    # double space a removed quote leaves behind and ALSO ate every paragraph
    # break in the story, because `\s` is newlines too.
    #
    # That is the whole reason narrator prose was arriving unbroken. Three
    # contracts were built and measured against a model that was often doing
    # its part -- the blank-line instruction's 1% and the marker contract's
    # live `paragraph_count` of 3, 4, 8, 10 both passed through here and came
    # out flat. The engine was deleting the breaks after the model wrote them.
    prose = re.sub(r"[^\S\n]{2,}", " ", prose)      # the spacing debris
    prose = re.sub(r"[^\S\n]*\n[^\S\n]*", "\n", prose)  # tidy around breaks
    prose = re.sub(r"\n{3,}", "\n\n", prose)        # never a blank run
    # A quote removed from between an attribution and its continuation leaves
    # the punctuation from BOTH sides ("You ask,, quietly"). The empty-quote
    # collapser above takes the marks; this takes the commas they sat between.
    prose = _DOUBLED_COMMA_RE.sub(",", prose)
    prose = re.sub(r"[^\S\n]+([,.!?])", r"\1", prose)   # " ," -> ","
    # A paragraph that BEGAN with the player's quote now begins with the
    # attribution that followed it, in lower case ("you ask it, your voice
    # clear..."). Nothing else in this function can see that a sentence lost
    # its head. Restoring the capital is safe here because narrator prose is
    # ordinary English paragraphs -- and it is the last visible trace of the
    # cut, so leaving it is leaving the seam on the page.
    prose = prose.strip()
    prose = re.sub(r"(\A|\n)([^\S\n]*)([a-z])",
                   lambda m: m.group(1) + m.group(2) + m.group(3).upper(),
                   prose)
    return prose


# An empty quote pair -- '' "" “” -- left where a stripped player line used to
# sit (Fable review, DW t12: "I can't hold her eyes. ''"). Collapse the orphan
# and heal the punctuation/space it leaves. Only a genuinely EMPTY pair is
# touched, so real quoted dialogue is never harmed.
#
# EMPTY MEANS ZERO CHARACTERS BETWEEN THE MARKS. `_EMPTY_QUOTE_RE` also carried
# `"\s*"` and `'\s*'`, which read any two quote marks separated only by
# whitespace as an empty pair -- and `\s` is a newline, so the alternative
# spanned a paragraph break. One speaker's close-quote and the next speaker's
# open-quote are exactly that shape once `narration._substitute_dialogue_tokens`
# has wrapped each delivered line in its own quotes, and `_strip_player_echo`
# above calls this unconditionally, so no player line and no strip were needed
# to trigger it: the two marks went, and two speakers were welded into a single
# quoted string attributed to one voice while the reply was narrated again as if
# unspoken (15-beat trace, model output `{{L2}}</p><p>{{L3}}` correct, the
# dialogue_log record correct, only the rendered page wrong).
#
# Nothing in the engine can leave a whitespace-separated pair for this to
# collapse. Both removal paths in `_strip_player_echo` -- the literal
# `_QUOTE_PAIRS` form and the `_QUOTE_SPAN_RE` span -- delete the whole
# delimited span INCLUDING its marks, and so does `_cap_repeated_quotes`. A
# pair with anything at all between the marks is dialogue, not debris.


def _collapse_empty_quote_debris(prose):
    if not prose:
        return prose
    out = _ling("_EMPTY_QUOTE_RE").sub(" ", prose)
    # A lead-in left dangling against the removed quote ("She said, .", "then, .")
    out = re.sub(r"[,:]\s*\.", ".", out)
    out = re.sub(r"\s+([.,!?;])", r"\1", out)
    return out

def _phrase_ngrams(text, n):
    """Lower-cased n-word phrases of `text`, punctuation-stripped."""
    words = re.findall(r"[a-z']+", str(text or "").lower())
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


# Content words whose repetition is a genuine tic; function-word runs ("in the
# middle of") are not. A phrase must carry at least one of these to be flagged.


def _overused_phrases(recent_prose, current_prose="", n=3, min_hits=2, cap=12):
    """The narrator's own recurring set-dressing tics (Fable A4): short phrases
    that recur across recent turns' prose -- "the clock ticks", "thumps her tail
    once", "the fire settles". Fed back to the narrator as a ban list so it
    varies them, and used by the repetition check below.

    A phrase counts once per prose block it appears in (so a within-block
    repeat isn't inflated), must contain a content word, and must recur in at
    least `min_hits` blocks including the current draft when supplied.
    """
    blocks = [p for p in list(recent_prose or []) + [current_prose] if p]
    if len(blocks) < min_hits:
        return []
    counts = {}
    for block in blocks:
        for phrase in set(_phrase_ngrams(block, n)):
            words = phrase.split()
            if all(w in _ling("_TIC_STOPWORDS") for w in words):
                continue
            counts[phrase] = counts.get(phrase, 0) + 1
    # Prefer the longest/most-specific phrases; drop a phrase fully contained
    # in a longer flagged one so "clock ticks" and "the clock ticks" don't both
    # list.
    hits = sorted((p for p, c in counts.items() if c >= min_hits),
                  key=len, reverse=True)
    kept = []
    for phrase in hits:
        if not any(phrase in longer for longer in kept):
            kept.append(phrase)
    return kept[:cap]


#: Words that carry no content in a recycling comparison: the attribution
#: formula the composer emits around every line, and the label-shaped words a
#: descriptor is built from. Stripped before shingling, because a shingle is
#: supposed to catch a RECYCLED BEAT and these catch the same person speaking
#: twice.
#:
#: Measured, Enterprise run turns 8-15: four of five "reuse" findings were the
#: attribution itself -- `spare upright man says in a`, `the spare upright man
#: speaks in`, `the tall turns back to the`, `he turns in the command chair`.
#: Only one was real prose recycling. An unrecognised body renders by its
#: appearance ("the spare upright man"), which is FOUR words of a six-word
#: window before any content reaches it, so two unrelated sentences about one
#: stranger collide on the label alone.
_SHINGLE_STOPWORDS = frozenset({
    "says", "said", "say", "speaks", "spoke", "asks", "asked", "replies",
    "replied", "adds", "added", "answers", "answered", "in", "a", "an",
    "the", "his", "her", "their", "its", "with", "voice", "tone", "and",
    "then", "to", "of", "at", "on", "he", "she", "they", "it",
})


def _word_shingles(text, n=6, *, labels=()):
    """Six-word runs of CONTENT, for the recycled-prose comparison.

    `labels` are the display names in play this beat -- an unrecognised body's
    descriptor is long and recurs in every sentence about them, so leaving it
    in makes the label the match rather than the prose. Stripping the
    attribution vocabulary alongside it leaves the shingle measuring what it
    was built to measure: whether the BEAT was rewritten from an earlier one.
    """
    lowered = str(text or "").lower()
    for label in sorted((str(x or "").lower() for x in labels or ()),
                        key=len, reverse=True):
        if len(label) > 2:
            lowered = lowered.replace(label, " ")
    words = [w for w in re.findall(r"[a-z0-9']+", lowered)
             if w not in _SHINGLE_STOPWORDS]
    return {
        " ".join(words[i:i + n])
        for i in range(len(words) - n + 1)
    }

def _already_established_phrases(view, recent_prose, limit=12):
    """Deterministic overlap between THIS turn's raw view and the narrator's
    own recent prose.

    The narrator's job of "don't re-catalog what's unchanged" requires
    knowing what it already said, and having the model compare two blobs of
    prose itself is unreliable; this hands it a concrete, computed list.

    THIS DOCSTRING USED TO SAY the view re-describes the full room every
    turn because perception is "a stateless sensory filter with no memory of
    prior turns". That stopped being true when the composer began keeping a
    standing ledger: `render_view` suppresses standing state this observer
    was already given, so an ordinary beat's view has little left to overlap
    with. The claim survived in the narrator sheet as well, where it argued
    for a rule against a behaviour that no longer happens.

    What is actually true, measured over 2,294 stored beats in every chat on
    disk (2026-08-23): this returns something on 25.8% of them, and the rate
    is a property of the STORY rather than of the corpus -- 60% in chats 10
    and 12, 14-20% in the long-running ones. So the field is neither dead nor
    ordinary; it is emitted only when non-empty, and the sheet block it
    governs now says what an absent list means.
    """
    view_shingles = _word_shingles(str(view or ""))
    if not view_shingles:
        return []
    hits = set()
    for prev in recent_prose or []:
        hits |= (view_shingles & _word_shingles(prev))
    return sorted(hits)[:limit]

_YOU_RE = re.compile(r"\byou\b|\byour\b", re.I)


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
            for prefix in _ling("_PARTIAL_QUOTE_PREFIXES"):
                if c.startswith(prefix):
                    c = c[len(prefix):]
                    break
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
                   for m in _ling("_VIEW_QUOTE_BODY_RE").finditer(view)]
    boundaries = {0}
    inside = False
    for i, ch in enumerate(view):
        if ch in _ling("_QUOTE_CHARS"):
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
            npc = max((mm.start() for mm in _ling("_NPC_PRONOUN_RE").finditer(prefix)), default=-1)
            if name_re:
                npc = max([npc] + [mm.start() for mm in name_re.finditer(prefix)])
            if you < 0 or you <= npc:
                continue
            start, end = _clause_start(qs), qe
        else:
            cstart = _clause_start(qs)
            # Attribution cue for the dialogue-fidelity floor: a speech verb, or a bare
            # voice noun ("A muffled voice: ..."). Deliberately excludes reading verbs
            # (reads, is written/painted/carved, displays) so quoted ENVIRONMENTAL text --
            # signage, labels, screens -- is never mistaken for dialogue.
            pre_attr = bool(_ling("_DIALOGUE_CUE_RE").search(view[cstart:qs]))
            tstop = _tail_stop(qe)
            tail = view[qe:tstop]
            tail_lead = tail.lstrip()
            # A trailing attribution ('"...," she says.') continues the same
            # sentence, so it starts lowercase or with a dash -- an uppercase
            # tail is a NEW sentence and out of scope.
            tail_attr = bool(tail_lead) and (
                tail_lead[0].islower() or tail_lead[0] in ",—–-") \
                and bool(_ling("_DIALOGUE_CUE_RE").search(tail))
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


# Within-view dedupe (W12): the same sentence rendered twice in ONE turn's
# view/prose ("Picard turns his head slightly toward Troi" appearing twice in
# a single beat). Splitting is a plain sentence-boundary regex; a quote whose
# body contains sentence punctuation mis-splits into fragments, but every such
# fragment carries a quote character and is therefore exempt from dropping
# (below), so mis-splits can only UNDER-dedupe, never eat real content.
_VIEW_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])(\s+)")
_VIEW_DEDUPE_MIN_WORDS = 5

_VIEW_MASK = "\x00Q%d\x00"


def _mask_quoted_spans(text):
    """Replace each quoted span with a single opaque token.

    The token carries no whitespace and no terminal punctuation, so a sentence
    splitter cannot cut a quotation into pieces -- which is the whole point.
    Returns (masked_text, spans) for `_unmask_quoted_spans`.
    """
    spans = []

    def _swap(match):
        spans.append(match.group(0))
        return _VIEW_MASK % (len(spans) - 1)

    return _ling("_VIEW_QUOTED_SPAN_RE").sub(_swap, text), spans


def _unmask_quoted_spans(text, spans):
    for i, span in enumerate(spans):
        text = text.replace(_VIEW_MASK % i, span)
    return text


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

    QUOTED SPANS ARE MASKED BEFORE SPLITTING, because that first rule was
    defeated by the splitter for years. The check is per-SENTENCE ("does this
    fragment contain a quote character"), and a spoken line containing its own
    terminal punctuation is cut into several fragments -- only the two on the
    ends keep a quote mark, and every fragment between them is judged naked and
    dropped if it echoes anything earlier in the view.

    Live (chat 58, t30). The player answered a direct question with "Seven? I
    think? There might have been more... they began to spread out..." -- four
    terminators, so four fragments. This runs LAST in `perception_act`, after
    the deterministic delivery, and ate the interior of the quotation:

        Hinami says: "Seven? I think? There might have been more... they began
                      to spread out..."
        ->  Hinami says: "Seven? I think? they began to spread out..."

    The character then answered as though the line had never been said, asking
    the question that had just been answered. Perception_act is the view a
    character DECIDES from, so unlike a narrator-side drop this is invisible in
    play -- it surfaces only as a non-sequitur that reads like a model failure.

    Returns the text unchanged (same object) when nothing repeats.
    """
    text = str(text or "")
    if not text.strip():
        return text
    masked, spans = _mask_quoted_spans(text)
    pieces = _VIEW_SENTENCE_SPLIT_RE.split(masked)
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
            # A masked span means this sentence carries a quotation. The raw
            # check stays alongside it for an UNTERMINATED quote, which the
            # span regex cannot match and which must still be protected.
            and "\x00" not in sent
            # Double-quote characters only: curly/straight single quotes double as
            # apostrophes in ordinary prose and cannot mark dialogue reliably. The
            # pack names them, because which glyphs open a spoken line is the one
            # thing about dialogue that every language answers differently.
            and not any(qc in sent for qc in _ling("_QUOTE_CHARS"))
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
    return _unmask_quoted_spans("".join(kept).rstrip(), spans)

#: A doubled opening mark makes the paired pattern match an EMPTY span and
#: desynchronise every quote after it on the line -- observed live. Folded to
#: one mark before pairing rather than special-cased afterwards.
#: An opening mark with no partner, running to end of line. Applied only after
#: the paired passes, so it can only ever catch what is genuinely unclosed.
# Third-person player evidence comes almost entirely from the player's NAME
# used as a proper noun; pronouns are inherently ambiguous ("her"/"him"/
# "them" nearly always refer to OTHER people in the scene). We therefore
# count only subjective-form player pronouns and never object/possessive
# ones -- and even those only survive as a tiebreak once hysteresis in
# _resolve_narration_person guards against a lone token flipping the whole
# campaign's established person.

def _narrative_outside_quotes(text):
    """`text` with quoted dialogue removed, in the ACTIVE story pack's quote
    marks. Everything a speaker says is somebody else's grammar: a "you" inside
    a spoken line addresses a character rather than the reader, and a spoken
    verb is in whatever tense that character is speaking in. Both of the
    whole-draft detectors below score the narrating voice only, so both start
    here.

    Whatever quote mark is left opened dialogue that never closed, so the rest
    of the line is dialogue too. Folded in here rather than guarded at the call
    sites, because a guard that must be remembered will be forgotten and this
    one was: the paired pattern needs a closing mark, so an unterminated quote
    let every "I" and "my" inside the speech vote on how the NARRATION should
    read. Rare and decisive -- 11 of 2163 live player turns change verdict, and
    one of them latched a whole story into first person.
    """
    narrative = _ling("_NARRATION_DOUBLED_QUOTE_RE").sub('"', str(text or ""))
    narrative = _ling("_NARRATION_QUOTE_RE").sub(" ", narrative)
    narrative = _ling("_NARRATION_SQUOTE_RE").sub(" ", narrative)
    return _ling("_NARRATION_DANGLING_QUOTE_RE").sub(" ", narrative)


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
    narrative = _narrative_outside_quotes(raw_input)
    counts = {
        "first": len(_ling("_FIRST_PERSON_RE").findall(narrative)),
        "second": len(_ling("_SECOND_PERSON_RE").findall(narrative)),
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
        if pron in _ling("_THIRD_SUBJECT_PRONOUNS") and pron not in seen_pronouns:
            seen_pronouns.add(pron)
            counts["third"] += len(re.findall(rf"\b{re.escape(pron)}\b", narrative, re.IGNORECASE))
    return counts

# Third-person paradigms screened by _check_pronoun_fidelity. Only these three
# closed sets are checked: a character whose declared pronouns fall outside the
# table (neopronouns, mixed sets like she/them) is skipped entirely rather than
# guessed at -- the check exists to catch UNAMBIGUOUS flips, so anything it
# can't be certain about is not its business.
def _pronoun_to_group():
    """Pronoun -> group, for the ACTIVE story pack.

    Built at MODULE level before, which evaluated `_ling` once at import with
    the contextvar still at its "en" default. The Japanese pack deliberately
    adds 彼/彼女/彼ら groups and every one of them was dead, so the pronoun
    fidelity check silently returned nothing for a Japanese story. This is the
    exact hazard `linguistic()`'s own docstring warns about: the lookup has to
    happen at use time, because two languages can run in one process.
    """
    return {w: g for g, ws in _ling("_PRONOUN_GROUPS").items() for w in ws}

# Splits a sentence into clauses. A pronoun is only scored against a name in
# the SAME clause, which is what keeps "Vorne glanced at the ensign; her hands
# shook" (referent is the ensign, not Vorne) out of the check.
#
# The CJK branch takes no trailing whitespace, because Japanese writes none
# after 。 -- an ASCII-only splitter returned the whole passage as one clause,
# so every pronoun scored against every name in it.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])[」』\"\'”’)\]]*\s*")

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
        group = _pronoun_to_group().get(word)
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
        for token in _name_tokens(canonical):
            if len(token) < _name_token_floor(token):
                continue
            # The capital is what separates a name part from an ordinary word
            # it sits beside -- in a script that HAS capitals. Demanding one of
            # a caseless script drops every token, which is how this guard came
            # to return [] for a Japanese cast before consulting a pronoun at
            # all. Same reasoning as `_player_name_forms`.
            if not _UNSPACED_SCRIPT.match(token[:1]) and not token[:1].isupper():
                continue
            # Names that are also ordinary capitalized English words. A cast member called
            # one of these can't be told apart from the common word, so we decline to score
            # their clauses rather than burn a rewrite on "Will you hand him the padd".
            if token.lower() in _ling("_AMBIGUOUS_NAME_WORDS"):
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
    scan = _ling("_NARRATION_QUOTE_RE").sub(" ", prose)

    warnings = []
    flagged = set()
    for sentence in split_sentences(scan, _SENTENCE_SPLIT):
        for clause in _ling("_CLAUSE_SPLIT").split(sentence):
            # MEASURED BEFORE ENFORCING, because this warning's prefix is in
            # `_ENFORCEABLE_PREFIXES` and a false positive buys a full narrator
            # rewrite. Replayed over every stored narrator variant in the live
            # database (2,350 with prose, 69,589 clauses): 0 clauses tokenise
            # differently. `_NAME_TOKEN_RE` opens with the same `[A-Za-z']+`,
            # so the English answer is unchanged by construction and the whole
            # of the new exposure is in scripts where this guard returns
            # nothing at all today.
            words = _name_tokens(clause)
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
            # A POSSESSIVE name is not the clause's SUBJECT, so a pronoun after
            # it does not refer back to that name. "Sarah Moon's orders reach
            # him" has `orders` as its subject and `him` as an object naming
            # somebody else -- live, chat 84 t13, where `him` was the guard
            # standing in the room and this fired an enforceable mismatch
            # against a doctor who was not its referent. The check cannot see
            # the guard at all: he is a background presence, not registered
            # cast, so `present` held exactly one name and the clause looked
            # unambiguous. Declining on the possessive costs a miss on
            # "Vorne's hand trembles as she reaches" and buys back every
            # clause of this shape, which is the trade this whole check is
            # written to make.
            if any(re.search(rf"(?<![\w']){re.escape(tok)}['\u2019]s(?![\w])",
                             clause)
                   for tok in _name_tokens(canonical)):
                continue
            for word in words[head + 1:]:
                other = _pronoun_to_group().get(word.lower())
                # A stray "they" is routinely a group ("Vorne watched them
                # scatter"), so only a GENDERED singular counts as a flip.
                if not other or other == group or other == "they":
                    continue
                key = (canonical, word.lower())
                if key in flagged:
                    break
                flagged.add(key)
                expected = "/".join(_ling("_PRONOUN_GROUPS")[group][:3])
                warnings.append(
                    f"Pronoun mismatch for '{canonical}' (canonical {expected}): "
                    f"prose renders '{word}'"
                )
                break
    return warnings


def _check_player_person(prose, player_name, narration_person, player_aliases=None):
    """Deterministic backstop for the narrator's PERSON DISCIPLINE rule.

    When narration_person is 'second' or 'first', the player character is
    'you'/'I' -- naming them is, in the prompt's own words, a hard error. The
    rule was prompt-only, so a player_view that named the player (see
    _self_second_person for how the engine itself used to do that) produced
    prose mixing persons for one character with nothing to catch it, and the
    competing PROPER NOUN FIDELITY instruction actively pushed the model to
    copy the name through.

    Name-based only, and outside quoted spans: a character ADDRESSING the
    player by name aloud is legitimate dialogue that must survive verbatim,
    and a third-person descriptor ('the traveller') cannot be distinguished
    from a reference to someone else without resolving it -- so this scores
    the one signal that is unambiguous.
    """
    person = str(narration_person or "").strip().lower()
    if person not in ("second", "first"):
        return []
    text = str(prose or "")
    if not text:
        return []
    segments = _ling("_QUOTED_SPAN_RE").split(text)
    hits = []
    for form in [player_name, *(player_aliases or [])]:
        form = str(form or "").strip()
        if not form:
            continue
        flags = 0 if form.casefold() in _ling("_COMMON_WORD_NAMES") else re.I
        pattern = re.compile(
            r"(?<!\w)" + re.escape(form) + r"(?:['’]s)?(?!\w)", flags)
        for i in range(0, len(segments), 2):  # even indices = unquoted prose
            if pattern.search(segments[i]):
                hits.append(form)
                break
    if not hits:
        return []
    pronoun = "you/your" if person == "second" else "I/me/my"
    return [
        "Player named in third person: narration_person is "
        f"'{person}', so the player character is {pronoun} and must never be "
        f"named in the prose -- found {', '.join(sorted(set(hits)))} outside "
        "quoted dialogue. Rewrite those references in the correct person, "
        "keeping every quoted line verbatim."
    ]


#: How far the prose's dominant person must lead the person that was ASKED
#: for before the mismatch is reported. Same margin as
#: `_resolve_narration_person`'s hysteresis, for the same reason: one stray
#: token is not a voice change.
_PERSON_DRIFT_MARGIN = 2


def _check_narration_person_match(prose, narration_person, player_name=None):
    """Did the narrator actually WRITE in the person it was told to.

    `_narration_person_counts` was called in exactly one place -- on the
    PLAYER's raw input, to decide `narration_person`. The narrator was then
    told "PERSON DISCIPLINE: ONLY the player character is 'I'/'me'/'my'" and
    nothing read the prose that came back. This is that missing half: the same
    detector, run over the output, warning when the dominant person disagrees
    with the person that was asked for.

    Reusing the detector rather than writing a second one is the point -- it
    already strips quoted dialogue (a "you" inside a spoken line addresses a
    character, not the reader), and unterminated-quote folding is the part
    that is easy to get wrong.

    Two deliberate narrowings, because this scores prose full of OTHER people:

    - third-person evidence comes from the player's NAME only
      (`player_pronouns` is not passed). Every other body on the page is
      legitimately "he"/"she"/"they", and the player's own pronouns are
      routinely the same words; counting them would report every beat where
      the cast moved more than the player did.
    - the dominant person must lead the declared one by `_PERSON_DRIFT_MARGIN`.

    Measured over the stored corpus (2,303 narrator drafts, per-turn person
    replayed from each turn's own input): 12 warnings, 0.52%, and every one of
    them is a real disagreement -- prose reading "Your words land in the
    corridor's flat hum" for a turn whose person resolved to `first`. It is a
    WARNING, never enforceable: a rewrite costs a whole narrator call, and
    person is a whole-draft property that a correction note cannot patch
    locally.

    **What it cannot catch, stated plainly:** it would NOT have caught the
    Director's observer-relative epithet reaching the player ("the young
    smith's apprentice" for the player's own body). That phrase is neither a
    name nor a pronoun, so it is invisible to every person detector. This is a
    backstop for genuine model non-compliance, not a fix for bad input --
    that fix is the composer's identity floor (`self_reference_forms`).
    """
    person = str(narration_person or "").strip().lower()
    if person not in ("first", "second", "third"):
        return []
    text = str(prose or "")
    if not text.strip():
        return []
    counts = _narration_person_counts(text, player_name, None)
    dominant = max(counts, key=counts.get)
    if dominant == person or counts[dominant] == 0:
        return []
    if counts[dominant] - counts.get(person, 0) < _PERSON_DRIFT_MARGIN:
        return []
    return [
        f"Narrator prose reads as {dominant} person but narration_person is "
        f"'{person}' ({counts['first']} first / {counts['second']} second / "
        f"{counts['third']} third-person markers outside quoted dialogue)."
    ]


#: How much verb evidence a draft must carry before its tense is scored at
#: all, and how far the asked-for tense must trail before the draft is
#: reported. Person is scored on a flat lead of 2 because its markers are
#: pronouns -- near-unambiguous, and a handful per paragraph. Tense markers are
#: verbs, they are noisier one by one, and a page written in one tense
#: legitimately carries some of the other: a past-tense narrative states
#: standing truths in the present ("the corridor runs east"), and a
#: present-tense one reaches back to what already happened. So the bar is a
#: RATIO over a floor, not a flat lead.
#:
#: Both numbers were chosen by measurement, not taste, on the author's stored
#: corpus (2,803 active narrator drafts, read from a read-only copy 2026-08-26).
#: Against 60 of them hand-labelled from their own opening sentences (random
#: sample, seed 11; 3 past, 57 present), floor 4 / ratio 2.0 scores 57 and
#: gets 57 right, declining the other 3 -- raising the floor to 8 only
#: declines more. Over the whole corpus it decides 2,575 of 2,803 (91.9%), and
#: 40 of those (1.55%) disagree with their own chat's dominant tense, which is
#: the measured rate of real mid-story drift (2-4%) rather than a noise floor.
#: On the one story that narrates in the past throughout, it reads past on 41
#: of 41 drafts.
_TENSE_MIN_EVIDENCE = 4
_TENSE_DRIFT_RATIO = 2.0


def _narration_tense_counts(text):
    """Past/present verb evidence from the narrating voice, outside quoted
    dialogue.

    The markers live in the pack (`_PAST_TENSE_RE`/`_PRESENT_TENSE_RE`) and
    each has two arms, deliberately SYMMETRIC -- a marker set that is richer on
    one side does not detect tense, it detects that side.

    The first arm is a closed list of auxiliaries, copulas and high-frequency
    irregulars whose form alone fixes the tense. On its own it is far too thin
    for this prose: measured over the 2,803 stored narrator drafts, the median
    draft is 124 narrative words and yields about 3 such markers, and 90% of
    drafts carry fewer than 8. The second arm is the inflection, anchored to a
    subject so that morphology is not read out of thin air -- a pronoun or a
    short determiner phrase followed by an `-ed` (past) or `-s` (present) word.
    A BARE `-ed` scan was rejected: an English past participle is also an
    adjective ("the closed door", "his folded hands"), and counting those
    scores every present-tense page as past.

    The anchored arms are not clean either -- "the open double doors" reads as
    a determiner phrase plus an `-s` verb -- which is why the verdict is a
    ratio rather than a majority, and why this returns COUNTS and decides
    nothing.

    Quoted speech is stripped first (`_narrative_outside_quotes`). That is the
    load-bearing part rather than a refinement: dialogue is present tense in a
    past-tense narrative by ordinary convention -- chat 6 ran 41 of 41 stored
    drafts in first-person past with present-tense speech throughout -- so a
    detector that read the quotes would report every correct past-tense draft
    as drift.
    """
    narrative = _narrative_outside_quotes(text)
    return {
        "past": len(_ling("_PAST_TENSE_RE").findall(narrative)),
        "present": len(_ling("_PRESENT_TENSE_RE").findall(narrative)),
    }


def _check_narration_tense_match(prose, narration_tense):
    """Did the narrator actually WRITE in the tense it was told to.

    The same shape as `_check_narration_person_match` above, and the same
    verdict about what to do with the answer: it is a WARNING and it is
    deliberately NOT in `_ENFORCEABLE_PREFIXES`. A rewrite costs a whole
    narrator call, and tense -- like person -- is a whole-draft property that a
    correction note cannot patch locally.

    It differs from the person check in what it may read. Person has a value on
    every turn because it is DETECTED; tense is AUTHORED, so `""` is the
    ordinary case and means the author expressed no opinion. Nothing is scored
    then: an unset story gets no payload field, no instruction and no warning,
    which is what makes this whole feature invisible to a story that did not
    ask for it.
    """
    # The vocabulary is `story.scene.NARRATION_TENSES`; it is spelled out here
    # rather than imported for the same reason the person check spells out its
    # three values -- this module is imported by every role module and owes
    # `story.scene` nothing. Anything else, including the empty string every
    # unset story sends, falls through to silence.
    tense = str(narration_tense or "").strip().lower()
    if tense not in ("present", "past"):
        return []
    text = str(prose or "")
    if not text.strip():
        return []
    counts = _narration_tense_counts(text)
    other = "present" if tense == "past" else "past"
    if counts["past"] + counts["present"] < _TENSE_MIN_EVIDENCE:
        return []
    if counts[other] < counts[tense] * _TENSE_DRIFT_RATIO:
        return []
    return [
        f"Narrator prose reads as {other} tense but narration_tense is "
        f"'{tense}' ({counts['past']} past / {counts['present']} present-tense "
        "verb markers outside quoted dialogue)."
    ]


def _flexible_quote_re(body, flags=re.I):
    """Regex matching a quote body verbatim but whitespace-flexible (the
    narrator may re-wrap lines) and terminal-punctuation-tolerant (English
    convention turns a line's final period into a comma before a trailing
    attribution: '"...," she says')."""
    body = re.sub(r"\s+", " ", str(body or "").strip())
    body = body.rstrip(".,!?…;: ")
    if not body:
        return None
    return re.compile(
        r"(?<!\w)" + r"\s+".join(re.escape(w) for w in body.split(" "))
        + r"(?!\w)", flags)


def _check_event_order(prose, event_order):
    """F1 (A1 ordering half): a quoted line must not render before the event
    it answers. event_order is the pipeline's own numbered causal record of
    this beat (player declaration first, then reaction/interaction rounds in
    call order, then parallel character declarations, then background
    reactions -- see agents/narration.py's _ordered_beat_events).

    Deterministic and conservative: only events whose quote appears VERBATIM
    in the prose are scored (DIALOGUE FIDELITY guarantees NPC lines do; the
    player's own echo-stripped lines simply won't match and are skipped), and
    only a strict position inversion between two located quotes fires."""
    if not prose or not event_order:
        return []
    quote_pattern = _ling("_QUOTE_BODY_RE")
    quote_spans = []
    for match in quote_pattern.finditer(strip_prose_markup(prose)):
        span = re.sub(r"\s+", " ", match.group(1).strip())
        if span:
            quote_spans.append((match.start(), span))

    located = []
    for ev in event_order:
        if not isinstance(ev, dict) or ev.get("kind") != "speech":
            continue
        body = re.sub(
            r"\s+", " ", _quote_body(str(ev.get("quote") or "")).strip())
        normalized = _fold_typography(body).casefold().rstrip(".,!?…;:")
        if len(normalized) < 3:
            continue
        # Locate a line only as a whole quoted span or a sentence-bounded line
        # region inside one. A plain substring search reads the player's short
        # ``More?`` as present inside an NPC's later ``More of that.``, then
        # reports the perfectly ordered answer as an inversion and spends
        # narrator rewrites trying to fix it. `_spoken_line_regions` retains
        # legitimate same-mouth multi-line spans without reviving that prefix
        # collision.
        at = None
        for start, span in quote_spans:
            if (_fold_typography(span).casefold().rstrip(".,!?…;:")
                    == normalized):
                at = start
                break
            regions = _spoken_line_regions(body, span)
            if regions:
                at = start + regions[0][0]
                break
        if at is not None:
            located.append((at, ev))
    warnings = []
    for (pos_a, ev_a), (pos_b, ev_b) in zip(located, located[1:]):
        if pos_b < pos_a:
            warnings.append(
                "Dialogue rendered out of order: "
                f"{ev_b.get('actor')}'s line "
                f"\"{_quote_body(ev_b.get('quote'))[:60]}\" appears in the "
                "prose BEFORE the earlier event it follows/answers "
                f"({ev_a.get('actor')}: "
                f"\"{_quote_body(ev_a.get('quote'))[:60]}\"). Render events "
                "in event_order's numbered order."
            )
    return warnings


def _check_action_direction(prose, event_order):
    """F5: an ACT listed in event_order, rendered in the wrong direction or
    dropped from the page entirely.

    An act is prose, not a quote, so unlike DIALOGUE FIDELITY there is no
    verbatim string to search for, and demanding a vocabulary match would
    force stilted wording ("the floor rising to meet him" is a correct
    rendering of a descent). Two findings, at different confidence:

    - REVERSED (enforceable): the act names exactly one direction and the
      prose names only the other. Judged without interpretation. From play:
      the Director resolved one character carrying another downward and the
      page rendered a lift.
    - MISSING (warning only): the act names a direction and the prose names
      neither. Legitimate prose can carry a descent with no directional verb
      at all, so this stays visible in fidelity_warnings for review rather
      than buying a rewrite it might not deserve.
    """
    if not prose or not event_order:
        return []
    # _NARR_LOWERING and _NARR_RAISING are deliberately TIGHTER than a natural
    # reading of "goes down" / "goes up": only verbs naming a deliberate directed
    # movement, plus the unambiguous adverbs. Bare "up"/"down" ("heat scorching up
    # your neck"), "rise"/"rose" (a chest rises; rose-gold motes) and "sink"/"drop"
    # all appear constantly in ordinary prose, and every one of them would turn
    # this into a false-positive generator that spends a rewrite on correct pages.
    p_low = bool(_ling("_NARR_LOWERING").search(prose))
    p_high = bool(_ling("_NARR_RAISING").search(prose))
    warnings = []
    for ev in event_order:
        if not isinstance(ev, dict) or ev.get("kind") != "action":
            continue
        act = str(ev.get("action") or "")
        a_low = bool(_ling("_NARR_LOWERING").search(act))
        a_high = bool(_ling("_NARR_RAISING").search(act))
        if a_low == a_high:
            continue                # the act says both directions, or neither
        said = "downward" if a_low else "upward"
        if (a_low and p_high and not p_low) or (a_high and p_low and not p_high):
            warnings.append(
                "Physical direction reversed: event_order has "
                f"{ev.get('actor')} moving {said} "
                f"(\"{act[:60]}\") but the prose renders the opposite. "
                "Render the act in the direction the record gives."
            )
        elif not p_low and not p_high:
            warnings.append(
                "Physical act from event_order may be missing in narrator "
                f"prose: {ev.get('actor')} moving {said} "
                f"(\"{act[:60]}\")."
            )
    return warnings


def _actor_reference_patterns(display):
    """Compiled patterns that count as a prose reference to one actor.

    A canonical proper name yields one case-sensitive pattern per usable name
    token (surname or first name alone is a normal reference). A descriptor
    label ('the unfamiliar woman', 'a woman in a gray uniform') yields one
    case-insensitive pattern for its content phrase minus the article."""
    display = str(display or "").strip()
    if not display:
        return []
    head = display.split()[0]
    # The pack's own article list -- the same one the compositor uses when it
    # BUILDS a descriptor label. A language with no articles supplies an empty
    # list and the leading-article branch simply never fires.
    articles = [str(a).lower() for a in (compositor_value("articles") or [])]
    article_re = ("^(?:%s)\\s+" % "|".join(re.escape(a) for a in articles)
                  if articles else None)
    proper = display[:1].isupper() or bool(_UNSPACED_SCRIPT.match(display[:1]))
    if head.lower() in articles or not proper:
        phrase = display
        if article_re:
            phrase = re.sub(article_re, "", phrase, flags=re.I)
        phrase = phrase.strip()
        if len(phrase) < _display_floor(phrase):
            return []
        return [re.compile(cue_boundary_pattern(
            r"\s+".join(re.escape(w) for w in phrase.split())), re.I)]
    pats = []
    for tok in _name_tokens(display):
        if len(tok) < _name_token_floor(tok):
            continue
        if not _UNSPACED_SCRIPT.match(tok[:1]) and not tok[:1].isupper():
            continue
        if tok.lower() in _ling("_AMBIGUOUS_NAME_WORDS"):
            continue
        pats.append(re.compile(cue_boundary_pattern(
            re.escape(tok) + r"(?:['’]s)?")))
    return pats


#: At or above this many characters a line is taken at FACE VALUE inside a
#: quoted span -- long enough that finding it there is not coincidence. This
#: used to be the only test, which silently exempted every line below it.
_MERGE_FACE_VALUE_CHARS = 15


def _spoken_line_regions(spoken, span):
    """Where this whole spoken line sits inside this one quoted span.

    A long line is matched plainly. A SHORT one is matched only where it
    stands as its own sentence -- bounded at the front by the span's start or
    a sentence ending, and closed by its own terminal punctuation or the end
    of the span.

    The length floor was there for a real reason: a short body can sit inside
    a longer one by coincidence, and this warning is ENFORCEABLE, so a false
    positive costs a rewrite. But a floor alone exempted exactly the lines
    that get absorbed -- short replies. Live, chat 84 turn 13: Sarah Moon's
    two lines and a guard's "Yes ma'am." (ten characters) were welded into a
    single quoted span, the guard never entered the comparison at all, and
    the span scored as one speaker with no warning raised.
    """
    if not spoken:
        return []
    if len(spoken) >= _MERGE_FACE_VALUE_CHARS:
        at = span.find(spoken)
        return [(at, at + len(spoken))] if at >= 0 else []
    ends = _ling("_SENTENCE_END_CHARS")
    out = []
    for match in re.finditer(re.escape(spoken), span):
        before = span[:match.start()].rstrip()
        if before and before[-1] not in ends:
            continue
        if spoken[-1] in ends or not span[match.end():].strip():
            out.append((match.start(), match.end()))
    return out


def _merged_span_actors(span, speech_events):
    """Which speakers' lines are actually inside this one quoted span.

    REGIONS, not membership, because one line can be a PREFIX or a tail of
    another speaker's longer line and the sentence-boundary test alone cannot
    tell that from absorption: Tamamo's "Go on." sits, correctly punctuated
    and correctly bounded, at the front of the Doctor's "Go on. I will wait
    here by the gate." Prose carrying only the Doctor's line is not a merge,
    and calling it one costs a rewrite.

    So a claim whose text is entirely accounted for by a LONGER line from a
    different speaker is coincidence and drops out. What survives is a line
    occupying text no longer line explains -- which is what absorption is.
    """
    placed = []
    for actor, spoken in speech_events:
        for start, end in _spoken_line_regions(spoken, span):
            placed.append((start, end, actor, len(spoken)))
    actors = set()
    for start, end, actor, length in placed:
        if any(other_actor != actor and other_len > length
               and other_start <= start and end <= other_end
               for other_start, other_end, other_actor, other_len in placed):
            continue
        actors.add(actor)
    return actors


def _check_quote_attribution(prose, event_order, actor_pronouns=None):
    """F4: a quoted line's nearest preceding actor reference must resolve to
    its actual speaker (prose convention assigns an unattributed quote to the
    nearest prior actor -- Enterprise t4 rendered Vorne's line right after
    'The unfamiliar woman pulls her hands back...', silently reassigning a
    tracked mind's speech to an anonymous body).

    Conservative by design -- it only fires when it POSITIVELY finds a
    different speaker's reference closer than the true speaker's:
    - a trailing attribution naming the true speaker clears the quote;
    - no locatable actor reference at all -> no call;
    - an intervening third-person pronoun whose gender differs from the
      nearest candidate's declared pronouns -> ambiguous, no call."""
    events = [ev for ev in (event_order or [])
              if isinstance(ev, dict) and ev.get("kind") == "speech"
              and ev.get("quote") and ev.get("actor")]
    if not prose or not events:
        return []
    # Reference patterns per distinct actor; a pattern text shared by two
    # actors identifies neither and is dropped.
    actors = list(dict.fromkeys(str(ev["actor"]) for ev in events))
    raw = {a: _actor_reference_patterns(a) for a in actors}
    owner = {}
    for a, pats in raw.items():
        for p in pats:
            owner.setdefault(p.pattern, set()).add(a)
    pat_map = {
        a: [p for p in pats if len(owner.get(p.pattern, ())) == 1]
        for a, pats in raw.items()
    }

    def _group_of(actor):
        return _pronoun_group((actor_pronouns or {}).get(actor))

    warnings = []
    flagged = set()
    for ev in events:
        expected = str(ev["actor"])
        body = _quote_body(str(ev.get("quote") or ""))
        if len(body) < 4 or body in flagged:
            continue
        qpat = _flexible_quote_re(body)
        m = qpat.search(prose) if qpat else None
        if not m:
            continue
        start, end = m.span()
        # Trailing attribution: same sentence right after the quote.
        tail = prose[end:end + 120]
        stop = re.search(r"[.!?\n]", tail)
        tail_seg = tail[:stop.end()] if stop else tail
        if any(p.search(tail_seg) for p in pat_map.get(expected, [])):
            continue
        # Leading scan: nearest actor reference between the previous quote
        # (or paragraph start) and this quote. The current quote's own
        # OPENING delimiter sits just before `start` and must not truncate
        # the context it opens.
        prefix = prose[:start].rstrip()
        while prefix and prefix[-1] in _ling("_QUOTE_CHARS"):
            prefix = prefix[:-1]
        cut = max(prefix.rfind("\n"),
                  max((prefix.rfind(qc) for qc in _ling("_QUOTE_CHARS")),
                      default=-1))
        prefix = prefix[cut + 1:]
        best = None  # (pos, actor)
        for actor, pats in pat_map.items():
            for p in pats:
                for mm in p.finditer(prefix):
                    if best is None or mm.start() > best[0]:
                        best = (mm.start(), actor)
        if best is None or best[1] == expected:
            continue
        # A gendered pronoun AFTER the nearest (wrong) candidate that does not
        # match that candidate's own declared pronouns re-points the reader
        # elsewhere ("Vorne nods. She says...") -- ambiguous, decline to call.
        between = prefix[best[0]:]
        cand_group = _group_of(best[1])
        ambiguous = False
        # The groups the ACTIVE pack declares, not three English words: the
        # Japanese pack adds 彼/彼女/彼ら groups and this scan could not see
        # any of them, so the ambiguity brake never engaged for a Japanese
        # story -- the same defect `_pronoun_to_group` was written to fix.
        groups = _pronoun_to_group()
        # EVERY FORM, not just the three subject pronouns. Iterating
        # `_PRONOUN_GROUPS` yields its KEYS -- he/she/they -- so an OBJECT or
        # POSSESSIVE pronoun ("him", "her", "them", "his") could never engage
        # this brake, and a sentence ending "...before Sarah Moon's orders
        # reach him." read to the check as containing no pronoun at all.
        # `_pronoun_to_group` already maps every form to its group; the brake
        # simply was not asking it. Live, chat 84 t13: the brake was the thing
        # that should have declined, and instead the guard's "Yes ma'am." was
        # reported as the doctor's -- an ENFORCEABLE finding, so a wrong call
        # here spends a whole extra narrator call.
        forms = sorted(_pronoun_to_group(), key=len, reverse=True)
        subject_re = re.compile(cue_boundary_pattern(
            "|".join(re.escape(w) for w in forms)), re.I)
        for pm in subject_re.finditer(between):
            pg = groups.get(pm.group(0).lower())
            if cand_group and pg and pg != cand_group:
                ambiguous = True
                break
        if ambiguous:
            continue
        flagged.add(body)
        warnings.append(
            f"Quote attributed to wrong speaker: \"{body[:60]}\" is spoken "
            f"by {expected}, but the nearest preceding actor reference in "
            f"the prose is {best[1]} and no attribution names {expected}. "
            "Make the true speaker the quote's clear owner."
        )
    return warnings


# Perception/gesture verbs that make a following room mention a LOOK, not a
# placement ("glances at the corridor"); they must not trip the position check.


def _check_position_fidelity(prose, position_facts, room_names):
    """F2: a character narrated at a room that differs from their committed
    position, with no movement event this beat, is a continuity break (DW t6:
    the Doctor mid-road; t7 renders him back in the TARDIS doorway).

    position_facts: [{name, room_id, moved}] -- display name, the room the
    scene commits them to THIS beat, and whether this beat's diff moved them.
    room_names: {room_id: display_name} for the rooms in play.

    Narrow: only a placement preposition (in/inside/within/into/at/back in)
    directly ahead of another room's display name, in a sentence whose nearest
    preceding actor reference is the unmoved character, fires."""
    if not prose or not position_facts:
        return []
    usable_rooms = {}
    for rid, rname in (room_names or {}).items():
        rname = str(rname or "").strip()
        if (len(rname) < _display_floor(rname)
                or rname.lower() in _ling("_GENERIC_ROOM_WORDS")):
            continue
        usable_rooms[rid] = rname
    warnings = []
    for fact in position_facts:
        if not isinstance(fact, dict) or fact.get("moved"):
            continue
        name = str(fact.get("name") or "").strip()
        own_room = fact.get("room_id")
        pats = _actor_reference_patterns(name)
        if not name or not own_room or not pats:
            continue
        own_name = str(usable_rooms.get(own_room) or "").lower()
        for sentence in split_sentences(prose, _SENTENCE_SPLIT):
            # Quoted speech is a speaker's claim, not narration.
            scan = _ling("_NARRATION_QUOTE_RE").sub(" ", sentence)
            best = max((mm.start() for p in pats for mm in p.finditer(scan)),
                       default=-1)
            if best < 0:
                continue
            for rid, rname in usable_rooms.items():
                if rid == own_room:
                    continue
                low = rname.lower()
                # A room whose name contains (or is contained by) the
                # character's own room's name cannot be told apart reliably.
                if own_name and (low in own_name or own_name in low):
                    continue
                # A language marks place with an adposition, and which SIDE of
                # the room name it sits on is the language's business, not this
                # guard's -- Japanese postposes it. The pack holds the whole
                # phrase with a {room} slot for that reason.
                shape = _ling("_PLACEMENT_PHRASE")
                place = re.compile(
                    str(shape["pattern"]).replace("{room}", re.escape(rname)),
                    int(shape.get("flags") or 0))
                pm = place.search(scan, best)
                if not pm:
                    continue
                if _ling("_LOOK_VERB_RE").search(scan[:pm.start()]):
                    continue
                warnings.append(
                    f"Character placed in wrong room: '{name}' is narrated "
                    f"in '{rname}' but this beat's committed position is "
                    f"'{usable_rooms.get(own_room, own_room)}' and no "
                    "movement occurred for them this beat. Keep them where "
                    "the scene puts them."
                )
                break
            else:
                continue
            break
    return warnings


def _check_portal_fidelity(prose, portal_states):
    """F3: named portal state in prose must match the committed scene (DW t9
    shuts the double doors; t12 renders 'through the open doors' with no
    open event). portal_states: {display_name: 'open'|'shut'} for portals the
    player can currently see (built in agents/narration.py)."""
    if not prose or not portal_states:
        return []
    scan = _ling("_NARRATION_QUOTE_RE").sub(" ", prose)
    warnings = []
    for name, state in portal_states.items():
        name = str(name or "").strip()
        state = str(state or "").strip().lower()
        if len(name) < _display_floor(name) or state not in ("open", "shut"):
            continue
        shape = _ling("_PORTAL_STATE")
        wrong = shape["shut"] if state == "open" else shape["open"]
        name_pat = str(shape["join"]).join(
            re.escape(w) for w in name.split()) or re.escape(name)

        def _asserted(form):
            return re.search(
                str(shape[form]).replace("{state}", wrong)
                                .replace("{name}", name_pat), scan, re.I)

        asserted = (
            # "the open doors" / "still-sealed hatch"
            _asserted("modifier")
            # "the doors ... stand open" (same clause)
            or _asserted("predicate")
        )
        if asserted:
            opposite = "shut" if state == "open" else "open"
            warnings.append(
                f"Portal state contradicts the scene: '{name}' is committed "
                f"{state} this beat, but the prose renders it {opposite}. "
                "Match the committed portal state exactly."
            )
    return warnings


# The player's own interiority, in the second person the narrator writes in.
# "you feel", "your terror", "terror grips you" -- the same boundary
# `_check_player_interiority_authority` defends on the Director's side, at the
# last stage before the reader.


# `_check_player_interiority_prose` LIVED HERE, and it is gone rather than
# demoted. It matched `_YOU_INTERIOR` -- a named-emotion list plus a verb
# list ("you feel", "you know", "you realise") -- against narrator prose in
# the second person, and it was ENFORCEABLE, so every firing bought a whole
# extra narrator call.
#
# It could not tell the two meanings of its own trigger apart. Second-person
# narration says "you feel" about SENSATION constantly, and that is the
# narrator doing its job: measured over 2,389 stored drafts it flagged 73
# (3.1%), and the sample reads "'you feel' in 'laps against your
# shoulders'" -- water against a body, an observable the view delivered.
# The view-exemption did not save it, because the phrase it looked up was
# the bare trigger rather than the clause.
#
# It is the guard class this repo already has a name for: a literal matcher
# whose failure rate rises with how well the model writes. The rule it was
# defending is real and stays in the narrator sheet, and the DIRECTOR-side
# `_check_player_interiority_authority` is untouched -- that one matches a
# named subject in an omniscient sentence, which is a different and
# answerable question.


def _dialogue_tokens(view, p_lines):
    """The delivered lines, numbered, for the narrator to place not retype.

    THE MODEL CANNOT PARAPHRASE A LINE IT NEVER TYPES. That is the whole
    mechanism, and it is the move this codebase already made once: perception
    stopped repairing model prose when the composer began writing percepts,
    because chronology became a field rather than a pass. Dialogue fidelity is
    the same shape -- a property of the assembly, not a behaviour to request.

    Measured (`docs/experiments/NARRATOR_DIALOGUE_PLACEHOLDERS_2026-08-24.md`)
    on the beat that prompted it: 75% of delivered lines survived under the
    shipped prompt, 100% under this. The prompt was not the variable --
    DIALOGUE FIDELITY is already "ABSOLUTE", already says "NEVER SUMMARISE A
    SPOKEN LINE", and had already failed three times on that beat with the
    dropped lines named in correction notes.

    The player's own lines are excluded, because PLAYER ECHO RULE requires
    their ABSENCE -- handing them back as tokens to place would push the model
    to violate one rule to satisfy the other.
    """
    excluded = {
        re.sub(r"\s+", " ", _quote_body(q).casefold()).rstrip(".,!?…;:")
        for q in (p_lines or []) if _quote_body(q)
    }
    lines, seen = [], set()
    for match in _ling("_QUOTE_BODY_RE").finditer(str(view or "")):
        quote = re.sub(r"\s+", " ", match.group(1).strip())
        key = quote.casefold().rstrip(".,!?…;:")
        if not quote or key in excluded or key in seen:
            continue
        if _reads_as_attribution(quote):
            # NOT A LINE, AND WORSE THAN USELESS AS ONE. `_QUOTE_BODY_RE`
            # requires four characters between the marks, so a spoken line
            # shorter than that ("No.", "Aye.") is invisible to it -- and the
            # two quote marks it skipped then pair with their neighbours, so
            # the ATTRIBUTION between two short lines matches as a quote. The
            # fidelity check has always had this and merely gets confused by
            # it; handing it to the narrator as a line to place would put
            # "Riker says in a quiet voice:" on the page inside quotation
            # marks. Registered in `docs/UNBUILT.md`; guarded here.
            continue
        seen.add(key)
        lines.append(quote)
    return lines


#: The composer's own attribution formula. A span carrying one is the text
#: BETWEEN two quoted lines, never a line.
_ATTRIBUTION_TELLS = (" says in a ", " says in an ", " says under ",
                      " speaks in a ", " asks in a ", " replies in a ",
                      " says:", " speaks:", " asks:")


def _reads_as_attribution(text):
    lowered = " %s " % str(text or "").casefold()
    return any(tell in lowered for tell in _ATTRIBUTION_TELLS)



def _check_speech_marking(prose, view_quotes, excluded_bodies=()):
    """A delivered line that reached the page unquoted was re-costumed.

    DIALOGUE FIDELITY asks only whether the WORDS survived: `_contains_quote`
    strips markup for comparison (deliberately -- a tag inside a quote must
    not read as a dropped line) and then substring-searches, so an emphasised
    span with no quote marks passes it. Measured: view `Mara says in a quiet
    voice: "We should not be here."` with prose `She looks away. <i>We should
    not be here.</i>` raised no warning at all. A delivered line is SPEECH,
    and the page marks speech with quotation marks; the same words outside
    every quoted region are a different speech act, which is why the reader's
    own contract reserves emphasis for a thought the prose is voicing rather
    than quoting.

    Regions rather than a quote regex, the way the frontend and the schema
    both do it: `_QUOTE_BODY_RE` needs four characters between the marks, so
    a short line is invisible to it and the marks it skips then pair with
    their neighbours.

    The player's own lines are excluded: PLAYER ECHO RULE requires their
    ABSENCE, so their marking is a different rule's business.
    """
    scan = re.sub(r"\s+", " ",
                  _fold_typography(strip_prose_markup(str(prose or ""))))
    regions = [m.span() for m in _ling("_NARRATION_QUOTE_RE").finditer(scan)]
    folded = scan.casefold()
    warnings = []
    for quote in view_quotes or ():
        body = re.sub(r"\s+", " ",
                      _fold_typography(quote)).casefold().rstrip(".,!?…;:")
        if not body or body in (excluded_bodies or ()):
            continue
        placed, marked, at = False, False, folded.find(body)
        while at >= 0:
            placed = True
            end = at + len(body)
            if any(s <= at and end <= e for s, e in regions):
                marked = True
                break
            at = folded.find(body, at + 1)
        if placed and not marked:
            warnings.append(
                "Delivered line rendered without quotation marks: "
                f"\"{quote[:80]}\"")
    return warnings


def _check_attire_fidelity(prose, attire_facts):
    """A region the ledger still COVERS may not be narrated bare.

    The same shape as `_check_portal_fidelity`: a committed two-valued state
    and a prose assertion of its opposite. `attire_facts` is [{refs,
    covered}], built in agents/narration.py behind the same perception gate
    `_position_delta_payload` uses, so an unperceived body can never raise a
    warning about prose that rightly omits it.

    Three narrowings, each subtracting: quoted speech is scrubbed first (a
    speaker's CLAIM about a body is not narration); a partially exposed
    region never reaches `covered`; and the exposure word must be bound to
    the region noun by an ownership token of that body, so scenery is never a
    body.
    """
    if not prose or not attire_facts:
        return []
    shape = _ling("_EXPOSURE_STATE")
    scan = _ling("_NARRATION_QUOTE_RE").sub(" ", str(prose))
    # An idiom that names a REGION by accident -- being unarmed, not being
    # undressed. Masked at equal length so nothing shifts under a later match.
    scan = re.sub(str(shape["idiom"]), lambda m: " " * len(m.group(0)),
                  scan, flags=re.I)
    warnings = []
    for fact in attire_facts:
        refs = [re.escape(str(r)) for r in (fact.get("refs") or ()) if str(r)]
        if not refs:
            continue
        for region in (fact.get("covered") or ()):
            region = str(region or "").strip()
            if not region:
                continue
            pattern = (str(shape["assertion"])
                       .replace("{owner}", "|".join(refs))
                       .replace("{state}", str(shape["state"]))
                       .replace("{region}", re.escape(region)))
            if re.search(pattern, scan, re.I):
                warnings.append(
                    "Narrated exposure contradicts the attire ledger: the "
                    f"{region} is narrated bare while this beat's ledger "
                    "still has it covered. Describe it as the ledger has it.")
                break
    return warnings


def _check_narrator_fidelity(out, view, recent_prose=None, exclude_quotes=None,
                             cast_pronouns=None, player_name=None,
                             narration_person=None, player_aliases=None,
                             event_order=None, position_facts=None,
                             room_names=None, portal_states=None,
                             attire_facts=None, narration_tense=None):
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

    # A ONE-WORD NAME IS A NAME. The pattern above is `(?:...)+`, so it can
    # only ever see a proper noun of two or more capitalised words -- and a
    # single-token name is the commonest cast shape in this engine's own
    # stories, which made the check structurally unavailable for most of the
    # cast rather than merely quiet about them.
    #
    # Two questions, both of which the regex was guessing at. WHAT IS A NAME:
    # the roster is already in this payload, so the answer comes from the cast
    # rather than from capitalisation. WHAT COUNTS AS PRESENT: prose refers to
    # a person by pronoun after the first mention, which is ordinary English
    # and not a dropped body -- the multi-word arm gets that tolerance free
    # from its surname rule and a one-word name has no shorter form to fall
    # back on. Measured over 2,277 stored beats carrying both a view and
    # prose: without the pronoun tolerance this fires on 29 of 217 view-named
    # single-token cast members and 26 of those are pronoun prose; with it, 3.
    for name, pronouns in (cast_pronouns or {}).items():
        text = str(name or "").strip()
        if not text or len(text.split()) != 1 or text == player_name:
            continue
        if not re.search(rf"(?<!\w){re.escape(text)}(?!\w)", view_text):
            continue
        if text.lower() in prose.lower():
            continue
        forms = [str(pronouns.get(k) or "").strip().lower()
                 for k in ("subject", "object", "possessive")
                 ] if isinstance(pronouns, dict) else []
        if any(form and re.search(rf"(?<!\w){re.escape(form)}(?!\w)",
                                  prose.lower()) for form in forms):
            continue
        warnings.append(
            f"Proper noun from view missing in narrator prose: '{text}'")

    # past_narration is supplied to the narrator as the story's own text --
    # voice, rhythm and established detail -- but nothing stops the model
    # from reusing its content instead -- especially when the current view covers similar ground
    # (same room, same people) to a recent turn. Two or more shared
    # six-word runs between this turn's prose and a recent turn's prose
    # essentially can't happen by coincidence; it means this turn's beats
    # were recycled rather than drawn from the current view.
    # STRIP THE SPEAKERS FIRST. The labels in play come from the view, which
    # is where the composer wrote them -- a recognised name is short and
    # harmless, an unrecognised body's descriptor is long ("the spare upright
    # man") and recurs in every sentence about them, so two unrelated
    # sentences about one stranger overlap on the label rather than on any
    # recycled content. See `_word_shingles`.
    speaker_labels = set(re.findall(
        r"(?:^|[.!?]\s+)([A-Za-z][^.!?\n]{0,40}?)\s+(?:says|asks|replies|"
        r"speaks|adds|answers)\b", view_text))
    speaker_labels |= {str(x) for x in (player_aliases or ())}
    if player_name:
        speaker_labels.add(str(player_name))
    current_shingles = _word_shingles(prose, labels=speaker_labels)
    if current_shingles:
        for prev_prose in (recent_prose or []):
            overlap = current_shingles & _word_shingles(
                prev_prose, labels=speaker_labels)
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
        re.sub(r"\s+", " ", _quote_body(q).casefold()).rstrip(".,!?…;:")
        for q in (exclude_quotes or []) if _quote_body(q)
    }
    quote_pattern = _ling("_QUOTE_BODY_RE")
    normalized_prose = re.sub(r"\s+", " ", prose.casefold())
    view_quotes = []
    for match in quote_pattern.finditer(view_text):
        quote = re.sub(r"\s+", " ", match.group(1).strip())
        if not quote:
            continue
        view_quotes.append(quote)
        if quote.casefold().rstrip(".,!?…;:") in excluded_bodies:
            continue
        if not _contains_quote(normalized_prose, quote):
            warnings.append(
                f"Dialogue from view missing or altered in narrator prose: \"{quote[:80]}\""
            )

    # The inverse of dialogue preservation is equally absolute: a quoted line
    # the player-facing view never delivered has no authorised speaker. The
    # old check proved only that required quotes survived, so a draft could
    # keep every real line and add one more from the narrator. This happened
    # when a reaction-loop act vanished from perception and the narrator
    # guessed both the missing motion and a fresh NPC line.
    allowed_quotes = {
        re.sub(r"\s+", " ", quote.casefold()).rstrip(".,!?…;:")
        for quote in view_quotes
    }
    for match in quote_pattern.finditer(prose):
        quote = re.sub(r"\s+", " ", match.group(1).strip())
        normalized = quote.casefold().rstrip(".,!?…;:")
        if normalized and normalized not in allowed_quotes:
            warnings.append(
                "Narrator invented quoted dialogue absent from the player "
                f"view: \"{quote[:80]}\""
            )

    # ONE PAIR OF QUOTES, ONE MOUTH.
    #
    # The check above asks whether each line SURVIVED. It cannot ask whether
    # the line ended up in the right person's mouth, and both questions have
    # the same answer when two speakers' lines are welded into a single
    # quoted span: every body is present verbatim, so dialogue fidelity
    # passes while the reader is told the wrong character said half of it.
    #
    # Live (chat 38, t140): Tamamo's "Be at ease, both of you." and the
    # Doctor's "Tamamo. A pleasure." rendered as the single span
    # "Be at ease, both of you. Tamamo. A pleasure.", closed by "The Doctor's
    # voice carries clean across the clearing". The view had them correctly
    # separated, one attributed clause each. Also chat 38 t39, where the whole
    # of Guinan's line was absorbed into the Doctor's.
    #
    # `event_order` is the right source rather than the raw dialogue log: it
    # is already gated to lines that reached the player's view, so a line the
    # player never heard cannot raise a warning about prose that rightly
    # omits it. Bodies under 15 characters are ignored -- a short line can sit
    # inside a longer one by coincidence, and being wrong here costs a
    # rewrite.
    speech_events = []
    for event in (event_order or []):
        if not isinstance(event, dict) or event.get("kind") != "speech":
            continue
        # The player's OWN line is not this check's business. The echo rule
        # requires it to be ABSENT, so its presence is a different failure
        # with a different fix, and scoring it here would buy a rewrite for
        # the wrong reason. It has to be skipped explicitly rather than by
        # accident: it carried no `quote` at all until the narrator-package
        # work restored one.
        if event.get("declared"):
            continue
        actor = str(event.get("actor") or "").strip()
        spoken = re.sub(r"\s+", " ", _quote_body(event.get("quote"))).casefold()
        if actor and spoken:
            speech_events.append((actor, spoken))
    for match in _ling("_QUOTE_BODY_RE").finditer(prose):
        span = re.sub(r"\s+", " ", match.group(1)).casefold()
        actors = _merged_span_actors(span, speech_events)
        if len(actors) >= 2:
            warnings.append(
                "Merged dialogue from different speakers in one quoted span "
                f"({', '.join(sorted(actors))}): \"{match.group(1)[:80]}\""
            )

    warnings.extend(_check_pronoun_fidelity(prose, cast_pronouns))
    warnings.extend(_check_player_person(
        prose, player_name, narration_person, player_aliases))
    warnings.extend(_check_narration_person_match(
        prose, narration_person, player_name))
    # `narration_tense` is None on every story that has not set one, and the
    # check returns [] for it -- so this line adds nothing to the warning
    # stream of the 81 stories that predate the dial.
    warnings.extend(_check_narration_tense_match(prose, narration_tense))

    # F1-F4 world/ordering fidelity (all deterministic; each has its own
    # enforceable prefix in agents/narration.py so a violation buys exactly
    # one correction rewrite).
    warnings.extend(_check_event_order(prose, event_order))
    warnings.extend(_check_quote_attribution(
        prose, event_order, actor_pronouns=cast_pronouns))
    warnings.extend(_check_position_fidelity(
        prose, position_facts, room_names))
    warnings.extend(_check_portal_fidelity(prose, portal_states))
    warnings.extend(_check_action_direction(prose, event_order))

    # F5-F6: the page against the two records it was written from. Neither is
    # in `_ENFORCEABLE_PREFIXES` -- promotion is a measurement, not an edit.
    warnings.extend(_check_speech_marking(prose, view_quotes, excluded_bodies))
    warnings.extend(_check_attire_fidelity(prose, attire_facts))

    return warnings

def _llm_resolve_player_room(sc, pers, cast, interp, player_input):
    positions = sc.get("positions") or {}
    if not positions:
        return None
    char_names = []
    for c in (cast or []):
        try:
            char_names.append(character_name_from_text(c["sheet"]))
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
    try:
        out = jparse(chat_complete("utility", get_prompt("position_resolver"),
                                   json.dumps(payload, ensure_ascii=False),
                                   temperature=0.0, max_tokens=1000))
    except Exception as exc:
        # A provider failure and "the model found no match" used to be the
        # same answer here: both returned None, and the caller reported the
        # player's room as unresolved. They are different facts, and only one
        # of them is a system fault -- so the fault says so. The value is
        # still checked against `positions` before use, so this stays a
        # warning rather than a raise.
        note_step_warning(
            "position_resolver call failed (%s: %s); the player's room falls "
            "back to the committed position"
            % (type(exc).__name__, str(exc)[:120]))
        return None
    key = out.get("key") if isinstance(out, dict) else None
    if key and key in positions:
        return positions[key]
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
            char_names.add(character_name_from_text(c["sheet"]).lower().strip())
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


# ---- What the player asserts is true before anyone reacts to it ----
#
# THE RULE, from the person who owns the fiction: interpret is NOT a lesser
# authority than resolve. It is merely scoped to player input. If the player
# says something happens, it happens that turn -- before perception pass 1
# fires.
#
# It was not true, and the reason was structural rather than deliberate. A
# player's declaration reached `director_interpret` as prose and reached the
# SCENE only through `director_resolve`, which runs AFTER every character has
# declared. So everything a player narrated was invisible for the beat in
# which they narrated it: "I pull my top off" was perceived as still wearing
# it, "I kneel" as still standing, "I duck into the alcove" as standing in the
# open with no alcove. Each reactor decided against a world one beat stale,
# and the change surfaced the turn after.
#
# Contact, movement and following were each fixed one at a time, with their
# own field, their own guard and their own preview. That was the mistake --
# a hand-picked list of the channels lucky enough to have been noticed, each
# one re-deciding what the player is allowed to say. This is the general form,
# and it is deliberately not a shorter list of powers:
#
#   * THE SAME SCHEMA. `state_assertions` is a `StateDiff` -- the exact
#     structure `director_resolve` emits, every channel of it. Rooms, entities,
#     positions, conditions, world facts, destruction. Equal authority means
#     the same vocabulary, not a curated subset of it.
#   * THE SAME APPLIER. `merge_scene_with_diff` is what commit uses, and it is
#     pure and deep-copying, so pass 1 sees precisely the world commit will.
#   * SCOPED BY SOURCE, NOT BY SUBJECT. What bounds interpret is that it reads
#     the player's input and nothing else. There is no channel filter and no
#     per-subject guard here, because either would be this stage second-
#     guessing a declaration it was built to carry.
#
# What is NOT changed: commit remains the only writer. This previews on a copy
# for pass 1, and the assertion is merged into resolve's own diff so the beat
# is still persisted exactly once, through every guard commit already runs
# (occupied-room removal, destruction, room-registry projection). And the
# information firewall is untouched -- putting a fact into the scene is not
# putting it into a mind; the composer still admits it to an observer only if
# that observer can perceive it.


def validated_player_state_assertions(sc, raw, player_name, report=None):
    """The player's declared state changes, validated as a `StateDiff`.

    SHAPE ONLY, on purpose. An earlier pass of this filtered by channel and
    then by subject, which made interpret a lesser authority than resolve by
    construction -- exactly the thing this exists to stop being true. The
    Director already classifies each act `asserted` or `contestable`, and an
    act on somebody else IS contestable; deciding that is interpret's job,
    not a whitelist's.

    Pure: reads nothing, writes nothing, returns a plain dict.
    """
    if not isinstance(raw, dict) or not raw:
        return {}
    try:
        from llm.schemas import StateDiff
        clean = StateDiff(**raw).dict(exclude_unset=True)
    except Exception as exc:  # noqa: BLE001 - a malformed assertion is not a turn failure
        if report:
            report(f"discarded a malformed state assertion: {exc}")
        return {}
    clean = {key: value for key, value in clean.items() if value}

    # A DECLARED PLACE EXISTS, and the failure-proofing is to MINT it rather
    # than to refuse the position. Putting a body somewhere is the strongest
    # possible assertion that the somewhere is there -- `prepare_scene_commit`
    # already reasons exactly this way for a declared movement destination
    # (commit.py:2134), and an asserted position is the same claim by a
    # shorter route.
    #
    # Refusing it is the failure mode, not the fix: a position naming an
    # unknown room merges cleanly, commits, and leaves the body standing
    # nowhere -- no exception, no warning, a corrupt scene that persists, with
    # no room for perception to describe and no adjacency for movement to
    # walk. Dropping the position instead would just be the engine telling the
    # player their alcove is not real, which is the second-guessing this whole
    # channel exists to stop.
    #
    # The stub is deliberately minimal -- a name and an edge home. Mapping and
    # the Director furnish it; what matters here is that the place is on the
    # map and reachable, because an unreachable room is how an interior falls
    # out of the world.
    # ...BUT A PLACE NAMED AFTER A PERSON IS A RELATION TO THEM, NOT A PLACE.
    # The mint above asks whether the room exists and never whether the string
    # is a place at all, so a posture, a station or a hold written into
    # `positions` becomes a room and exiles the body into it. Measured live
    # (chat 95 t55): `positions: {"Hinami": "prone on Mirelle Sulmirath's
    # palm"}` minted a room of that name "with a way back to
    # private_session_room", and from that beat Hinami stood alone in it while
    # Mirelle stood in the session room. Contacts are pruned between bodies in
    # different rooms, so EVERY contact between them was dropped for the next
    # four turns -- including the interior contact of a swallow, which is what
    # `place_enclosed_bodies` needs to put her inside at all. The interior
    # rooms the Director correctly declared were never occupied, and both
    # minds were told about two people in two different places.
    #
    # The test is structural and reads the scene rather than English: does the
    # asserted room name a body the scene already knows. A real new place is
    # named for itself; a place named for somebody is `contained`, `contacts`,
    # `stations` or a pose, each of which has its own ledger and none of which
    # is this one. Rooms the beat DECLARES are exempt by the check above --
    # `mirelle_esophagus` arrives in `state_diff.rooms` with a `parent_entity`,
    # which is how an interior is supposed to enter the world.
    #
    # The position is dropped with it, deliberately: leaving it pointed at a
    # room that was refused is the corrupt-scene failure this whole block
    # exists to prevent. The body stays where it was, and the report names the
    # ledger that does hold the fact.
    def _names_a_body(room, scene):
        scene = scene if isinstance(scene, dict) else {}
        low = str(room or "").casefold()
        subjects = set(scene.get("positions") or {})
        subjects |= set(scene.get("attire") or {})
        for entity in (scene.get("entities") or {}).values():
            if isinstance(entity, dict) and entity.get("name"):
                subjects.add(str(entity["name"]))
        for subject in subjects:
            token = str(subject or "").strip().casefold()
            if len(token) > 2 and token in low and token != low:
                return str(subject)
        return ""

    positions = clean.get("positions")
    if isinstance(positions, dict) and positions:
        rooms = dict((sc or {}).get("rooms") or {})
        minted = dict(clean.get("rooms") or {})
        refused = []
        for who, room in positions.items():
            if not room or room in rooms or room in minted:
                continue
            named = _names_a_body(room, sc)
            if named:
                refused.append(who)
                if report:
                    report(f"asserted position put {who!r} in {room!r}, which "
                           f"names {named!r} rather than a place -- a relation "
                           "to a body is `contained`, `contacts`, `stations` "
                           "or a pose, never a room. Left them where they "
                           "were; state it in the ledger that holds it.")
                continue
            origin = ((sc or {}).get("positions") or {}).get(who)
            minted[room] = {
                "name": str(room).replace("_", " ").title(),
                "desc": "",
                "adjacent": ([{"to": origin, "barrier": "open",
                               "distance": "near"}]
                             if origin and origin in rooms
                             and origin != room else []),
                "notes": "",
            }
            if report:
                report(f"asserted position put {who!r} in {room!r}, which did "
                       "not exist; minted it with a way back to "
                       f"{origin!r}. Describe it if it matters.")
        for who in refused:
            positions.pop(who, None)
        if not positions:
            clean.pop("positions", None)
        if minted:
            clean["rooms"] = minted
    return clean


def preview_player_state_assertions(sc, assertions, ctx=None,
                                    player_name=None):
    """Apply asserted state to a scene COPY and return it.

    The copy is the whole safety property. Pass 1 and the resolving Director
    both need to see the world the player just described; neither may persist
    it. `merge_scene_with_diff` deep-copies before it touches anything, so the
    caller's scene is never the one that changes.

    TWO CALLS, in commit's own order, because commit makes two: attire is not
    a channel `merge_scene_with_diff` applies -- it has its own applier, since
    the removal ladder's clamp has to read the beat's prose to tell an
    undressing in progress from one that finished. A preview that merged and
    stopped would show every other channel changed and the body still dressed,
    which is the exact bug this exists to fix, reproduced inside the fix.
    """
    if not assertions:
        return sc
    merged = merge_scene_with_diff(sc, assertions)
    if assertions.get("attire") and ctx is not None:
        from persist.commit import apply_attire_diff
        # No resolve payload: the clamp's attribution reads
        # `ctx.turn.player_input`, which at pass 1 is the only account of this
        # beat that exists -- and the only one perception may ever have.
        apply_attire_diff(merged, {"attire": assertions["attire"]}, ctx, {},
                          report=False)
    return merged


def merge_player_state_assertions(assertions, resolved, player_name=None,
                                  report=None):
    """Carry asserted state into the durable diff.

    Previewing fixes what reactors SAW and nothing else -- if resolve then
    never mentions the change, commit writes the turn without it and the
    ledger forks from the beat everybody just played.

    Resolve keeps the last word and has to use it. Where resolve speaks about
    the same subject or key it is re-resolving, and it wins; silence is not a
    contradiction. Lists append rather than replace, since an op is an event
    and two events both happened.
    """
    out = dict(resolved) if isinstance(resolved, dict) else {}
    for channel, value in (assertions or {}).items():
        current = out.get(channel)
        if isinstance(value, dict):
            merged = dict(current) if isinstance(current, dict) else {}
            for subject, payload in value.items():
                if subject in merged:
                    if report:
                        report(f"resolve restated {channel} for {subject}; "
                               "the assertion yields")
                    continue
                merged[subject] = payload
            out[channel] = merged
        elif isinstance(value, list):
            existing = list(current) if isinstance(current, list) else []
            for item in value:
                if item not in existing:
                    existing.append(item)
            out[channel] = existing
        elif current in (None, "", 0):
            out[channel] = value
        elif report:
            report(f"resolve restated {channel}; the assertion yields")
    return out
