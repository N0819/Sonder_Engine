"""What a declared element is and what resolution made of it:
interior/autonomous act classification, communicative-act vocabulary, claim
dispositions and onset surfaces, authored-other-subject rerouting, target
binding, the reaction/resolution gates and authority-claim extraction.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from typing import NamedTuple
import re
from story.character_schema import (
    _UNSPACED_SCRIPT,
    cue_boundary_pattern,
    name_boundary_pattern,
)

from agents.common_base import (
    _base_from_third_person_s,
    _dict_list,
    _ling,
    _list,
    _stem_token,
)
from agents.common_names import _player_name_forms
from agents.common_cast import cast_spelling_policy


_REACTIVE_STAGES = {
    "preparation", "approach", "contact", "sustained",
}


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


#: The typed communicative acts the engine knows, each with the surface verb
#: it renders as: (third-person present, first-person past).  ONE table, not
#: one per tense -- review 2026-09-07 B14: the present forms lived here and the
#: past forms in `persist/commit_memory._first_person_sequence_text`, free to
#: disagree, so an act taught to one side rendered as bare "communicated" on
#: the other.  It is not a closed vocabulary of what a model may write: an act
#: outside it still renders, through `communication_verb`'s fallbacks.
COMMUNICATION_ACT_VERBS = {
    "ask": ("asks", "asked"), "question": ("asks", "asked"),
    "explain": ("explains", "explained"),
    "report": ("reports", "reported"), "tell": ("tells", "told"),
    "warn": ("warns", "warned"), "request": ("requests", "requested"),
    "offer": ("offers", "offered"), "instruct": ("instructs", "instructed"),
    "reassure": ("reassures", "reassured"),
    "promise": ("promises", "promised"), "admit": ("admits", "admitted"),
    "answer": ("answers", "answered"), "clarify": ("clarifies", "clarified"),
    "inform": ("informs", "informed"), "say": ("says", "said"),
}

#: The acts that leave their addressee owing an answer.  Review 2026-09-07 B14:
#: this set was spelled out twice -- `agents/character` building the player's
#: still-unanswered question, and `_asks_player` deciding whether the
#: interaction loop is still waiting on the player -- so the two could answer
#: "is this line awaiting a reply?" differently about the same event.  The
#: distinction is the act's DIRECTION: it puts something to its addressee for
#: them to supply or do, rather than only telling them something.
COMMUNICATION_ACTS_AWAITING_REPLY = frozenset({
    "ask", "question", "request", "instruct",
})


def communication_act(elem):
    """The typed act of a communicative element, read the one canonical way.

    Whitespace-collapsed and casefolded, because a model writing ``"Ask "``
    means the act one writing ``"ask"`` means.  Before B14 the surface renderer
    normalized it this way and the two awaiting-a-reply predicates did not, so
    a single event could be rendered as a question and treated as a statement.
    """
    if not isinstance(elem, dict):
        return ""
    act = " ".join(str(elem.get("act") or "").split()).casefold()
    # AN INFLECTED FORM OF A KNOWN ACT IS THAT ACT. A model writing "asks" or
    # "said" means the act the table spells "ask" or "say"; read raw, the
    # renderer conjugated it again ("sayss", "saids", "answerss" on the
    # playerless Aldermill run, 2026-09-23) and a question written "asks" was
    # never one that awaits a reply.
    return _COMMUNICATION_FORMS.get(act, act)


#: Each inflected form in `COMMUNICATION_ACT_VERBS`, back to its act. The
#: first act that claims a form keeps it ("asks" is `ask`, not `question`).
_COMMUNICATION_FORMS = {}
for _act, _forms in COMMUNICATION_ACT_VERBS.items():
    for _form in _forms:
        _COMMUNICATION_FORMS.setdefault(_form, _act)
del _act, _forms, _form


def communication_awaits_reply(elem):
    """Does this communicative act leave its addressee owing an answer?

    The only reader of `COMMUNICATION_ACTS_AWAITING_REPLY`: callers ask the
    question rather than re-spelling the vocabulary.
    """
    return communication_act(elem) in COMMUNICATION_ACTS_AWAITING_REPLY


def communication_verb(elem, tense="present", fallback=None):
    """Surface verb for a communicative act, in the tense the caller renders.

    The TABLE is shared; the fallback for an act outside it is the caller's,
    because that is a genuinely surface-local choice -- an observer's predicate
    guesses a present verb from the author's own word, while a first-person
    memory clause declines to guess an English past form and says
    ``communicated``.  Only the shared half was ever two representations.
    """
    act = communication_act(elem)
    known = COMMUNICATION_ACT_VERBS.get(act)
    if known:
        return known[1] if tense == "past" else known[0]
    if fallback is not None:
        return fallback
    if not act:
        return "said" if tense == "past" else "says"
    if tense == "past":
        return act
    # Already finite -- third person ("mutters") or past ("added") -- is
    # conjugated once: "addeds" reached Sal's view (playerless Aldermill
    # round 7, 2026-09-23). A past form reads as a tense slip in a present
    # view; re-conjugated it read as nothing. `-eed` is a base ("heed").
    head = act.split()[0]
    finite = _base_from_third_person_s(head) or (
        head.endswith("ed") and not head.endswith("eed") and len(head) > 3)
    return act if finite else act + "s"


def communication_surface(elem):
    """Observable indirect-speech predicate for a typed communicative act.

    The returned text is deliberately not a quotation.  ``content`` is the
    proposition the author supplied (ask what happened, explain the route),
    not words the engine is licensed to put in the speaker's mouth.
    """
    if not isinstance(elem, dict):
        return ""
    content = " ".join(str(
        elem.get("content") or elem.get("topic") or "").split())
    if not content:
        return ""
    return f"{communication_verb(elem)} {content}".strip()


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


def claim_disposition_rows(resolved):
    """Every claim-disposition row one resolution carries, in order.

    A resolve names its adjudications in two places -- the top-level
    ``claim_dispositions`` and the same key inside ``state_diff`` -- so
    "which rows are this resolution's" is asked here once instead of once
    per reader. Diff rows come second, which is the order the reconciler's
    claim-id index relies on to let the diff have the last word.
    """
    resolved = resolved if isinstance(resolved, dict) else {}
    rows = [row for row in (resolved.get("claim_dispositions") or [])
            if isinstance(row, dict)]
    sd = resolved.get("state_diff")
    if isinstance(sd, dict):
        rows.extend(row for row in (sd.get("claim_dispositions") or [])
                    if isinstance(row, dict))
    return rows


class ClaimScan(NamedTuple):
    """What one action's claim dispositions say about it.

    ``statuses`` and ``claim_ids`` are the rows that bear on the action, in
    the order resolution named them; ``realized`` is whether resolution made
    the whole of the action true.
    """

    statuses: list
    claim_ids: list
    realized: bool


def scan_claims_for(elem, resolved):
    """The claim dispositions that speak for one declared action.

    Finding B13 (2026-09-07 review): this scan lived twice -- in
    ``_claim_realized`` (which decides the sequence verdict a phase gets)
    and in ``adjudicated_player_action_text`` (which decides how much of the
    player's declared surface the narrator and perception may show). One
    question about one act cannot have two answers, so it has one scan.

    A row bears on the action when it names the event id outright, or when
    it is an intent claim of the same sequence index
    (``claim:<index>:<kind>:<n>``) -- several of those can belong to one
    multi-phase action, and one realized effect must not promote its
    deferred siblings to completed fact. With no such row, the action counts
    as realized only when some realized row lists its event id in
    ``realized_event_ids``.
    """
    event_id = str((elem or {}).get("event_id") or "").strip()
    match = re.search(r":player:(\d+):action$", event_id)
    sequence_idx = match.group(1) if match else None
    statuses, claim_ids = [], []
    realized_ids = set()
    for row in claim_disposition_rows(resolved):
        claim_id = str(row.get("claim_id") or "").strip()
        status = str(row.get("status") or "").casefold()
        if status == "realized":
            realized_ids.update(
                str(value).strip()
                for value in (row.get("realized_event_ids") or [])
                if str(value).strip())
        if claim_id == event_id or (sequence_idx is not None and
                claim_id.startswith(f"claim:{sequence_idx}:")):
            statuses.append(status)
            claim_ids.append(claim_id)
    if statuses:
        realized = all(status == "realized" for status in statuses)
    else:
        realized = bool(event_id and event_id in realized_ids)
    return ClaimScan(statuses, claim_ids, realized)


def _claim_realized(elem, resolved):
    """Whether resolution explicitly realized every claim for one action."""
    if str(elem.get("commitment") or "") != "contestable":
        return True
    return scan_claims_for(elem, resolved).realized


def _scene_has_subject(scene, subject, canonical=None):
    """Is this declared participant a body the scene holds?

    BLOCKING IS A STATEMENT ABOUT PRESENCE, NEVER ABOUT SPELLING (review
    2026-09-07 A34). A "no" here blocks the phase, and
    `prune_blocked_phase_changes` then deletes every state record sourced
    from it -- so a participant this misses is a change the beat loses.

    Two ways it used to answer "no" about a body that was standing there:

    - The self-reference forms were nine English literals, so a sequence
      written in another language -- the pack's own second-person or
      reflexive word -- named a "missing participant" on every beat. The
      set is the pack's (`_PARTICIPANT_SELF_FORMS`).
    - The scene's own keys were compared literally, so a participant
      written as the sheet uid or `character:<id>` -- both spellings the
      engine itself hands out -- matched nothing. `canonical` is
      `cast_spelling_policy`'s resolver: pass it and every spelling a
      registered body answers to resolves to the one the scene is keyed by.
    """
    wanted = str(subject or "").strip().casefold()
    if not wanted or wanted in _ling("_PARTICIPANT_SELF_FORMS"):
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
    if wanted in candidates:
        return True
    if canonical is None:
        return False
    resolved = str(canonical(subject) or "").strip().casefold()
    if not resolved:
        return False
    if resolved != wanted and resolved in candidates:
        return True
    # Both ends through the same resolver: the scene may be keyed by the uid
    # while the sequence names the sheet, which is the mirror of the case
    # above and just as much a body that is present.
    return any(resolved == str(canonical(key) or "").strip().casefold()
               for key in candidates)


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


def settle_sequence_dispositions(sequence, resolved, scene,
                                 cast=None, player_name=None):
    """Compose model adjudication with explicit causal prerequisites.

    The model decides contested outcomes.  The engine decides the structural
    consequence: a dependent phase cannot execute when its prerequisite was
    merely attempted, when a named participant does not exist, or when a
    required standing contact is absent.

    `cast`/`player_name` are the spelling tolerance (A34): the presence test
    resolves a participant through `cast_spelling_policy` so a body named by
    its uid or `character:<id>` is the body the scene already holds. Absent
    them the test falls back to literal scene keys, which is what every
    caller had before.
    """
    verdicts = []
    by_key = {}
    canonical = (cast_spelling_policy(cast, player_name)[0]
                 if (cast or player_name) else None)
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
                       if not _scene_has_subject(scene, person, canonical)]
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


def _record_source_event(record):
    """The event id a record cites, whichever of the two fields carries it.

    `from_event` is checked FIRST because it is the field the sheets now ask
    for; a record carrying both agrees with itself in every case measured, and
    where it would not, the typed field is the one the engine declared.
    Zero is not provenance (`director_evidence._drop_zero_provenance`), so it
    reads as no citation rather than as event 0.
    """
    if not isinstance(record, dict):
        return ""
    for field in ("from_event", "source_event_id"):
        value = record.get(field)
        if value in (None, "", 0, "0"):
            continue
        return str(value)
    return ""


def prune_blocked_phase_changes(diff, dispositions):
    """Drop state-diff records explicitly sourced from a blocked phase.

    Specialists cite the event a record came from two ways, and this reads
    both. ``from_event`` is a field OF the record and stays on it -- the
    evidence seam cites it and `story/attire.py` resolves it -- while inline
    ``source_event_id`` is a compatibility input and is stripped before
    persistence. ``phase_sources``, a sidecar mapping channel path or list
    index to event id, is read first and popped.

    Untagged output is left alone; this floor never guesses which change a
    prose sentence meant.
    """
    if not isinstance(diff, dict):
        return []
    # An id of "" or 0 is NOT an id. It has to be dropped here rather than
    # compared against, because an untagged record cites "" too, and one
    # blocked row with no id would take the whole diff with it.
    blocked = {
        str(row.get("event_id")) for row in dispositions or []
        if isinstance(row, dict) and row.get("status") == "blocked"
        and row.get("event_id") not in (None, "", 0, "0")
    }
    if diff.get("causal_steps"):
        from world.causal_program import prune_program
        return prune_program(diff, blocked)
    dropped = []
    phase_sources = diff.pop("phase_sources", {})
    numeric_list_drops = {}
    if isinstance(phase_sources, dict):
        for path, source in phase_sources.items():
            source = "" if source in (None, "", 0, "0") else str(source)
            if not source or source not in blocked:
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
                source = _record_source_event(record)
                if source and source in blocked:
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
                source = _record_source_event(record)
                if source and source in blocked:
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
    scan = scan_claims_for(elem, resolved)
    if scan.realized:
        return surface
    # An intent-only alternative that was wholly deferred/rejected never
    # began. A direct event disposition of "deferred" is different: the
    # attempted onset may have happened before its effect was prevented.
    intent_only = bool(scan.claim_ids) and all(
        claim_id.startswith("claim:") for claim_id in scan.claim_ids)
    if intent_only and not any(
            status in ("realized", "begun", "contested")
            for status in scan.statuses):
        return ""
    return observable_action_onset_text(elem)

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
            # "Opens with the name" judged in the name's own script (A2): an
            # unspaced script writes the next morpheme straight onto the
            # name, so demanding a space or an apostrophe after it matched
            # nothing at all. Latin forms keep the separator test exactly.
            if _UNSPACED_SCRIPT.match(str(form)[:1]):
                if not re.match(name_boundary_pattern(form), low):
                    continue
            elif not any(low.startswith(form + suf)
                         for suf in (" ", "'", "’")):
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
            # The name's own boundary (A2), as in shape 1 above.
            hit = re.search(name_boundary_pattern(form), low)
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
            # Each name's own boundary, not `\b` (A2): a name followed
            # directly by a particle is still that name, and an act that
            # binds nobody is invisible to the reaction gate, to claim
            # subject binding and to perception's targeted-observer check
            # alike. Identical for Latin names.
            if any(re.search(name_boundary_pattern(form), haystack)
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
        # The engine's own handle (`character:<id>`) binds a target as much
        # as the id or the name does -- a prose-contract row writes a cast
        # target either way, and this gate read only the other two (the
        # class `normalize_character_refs` names).
        handle = text[10:] if text.startswith("character:") else ""
        if handle.isdigit() and int(handle) in valid_actor_ids:
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
    return bool(acts_awaiting_resolution(result))


def acts_awaiting_resolution(result):
    """The declared actions `_requires_director_resolution` answers for: the
    acts nobody can answer until the world says what happened, in order.

    One predicate, two projections. The interaction loop needs WHICH acts
    are waiting -- a speaker it calls again this beat is told what it tried
    that the world has not answered yet (`decision.not_answered_yet`) -- and
    a second copy of these three tests would be free to disagree with the
    exit that ended the stretch.
    """
    waiting = []
    for action in _dict_list(result.get("sequence")):
        if action.get("type") != "action":
            continue
        text = str(action.get("attempt") or "").casefold()
        if (action.get("visibility") == "concealed"
                or action.get("commitment") == "contestable"
                or any(term in text for term in _ling("_CONFLICT_VERBS"))):
            waiting.append(action)
    return waiting

def _classify_action_commitment(raw_text):
    """Classify an action as asserted or contestable.

    The pack's `ATTEMPT_CUES` table is the AUTHORITY on what marks an
    unfinished attempt; the director_interpret sheet states the class and
    illustrates it, and its illustrations are not this table. This function is
    a BACKSTOP only -- `_extract_claims` calls it just where the Director
    omitted `commitment` outright, so a mislabelled `asserted` never reaches
    it. Review 2026-09-07 B29 measured the gap that leaves: the sheet named
    six cues ('try', 'attempt', 'aim', 'rush', 'lunge', 'swing at') against
    sixteen here, so a Director reading the sheet as an enumeration can call
    "I reach for the pistol" a completed assertion and nothing downstream
    disagrees. Widen the TABLE when a new cue is caught; the sheet's job is
    the class, not the list.
    """
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
    or more than one (an ambiguous subject is worse than an absent one).

    Matched on each name's own boundary (A2): `\\b` cannot fall between a
    name and the particle written straight onto it, so in an unspaced script
    this found no cast member in any text and every claim's subject came back
    None. Identical for Latin names."""
    low = str(text or "").casefold()
    if not low.strip():
        return None
    hits = [
        display for display, forms in (target_forms or {}).items()
        if any(re.search(name_boundary_pattern(form), low) for form in forms)
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
