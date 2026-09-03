"""Player/major-character conduct becoming evidence in individual Charter minds.

The Director classifies ONE engine-authored source for the beat.  This module
answers the separate question for every Charter body: did that body actually
receive it?  Speech is admitted by the ordinary barrier/material hearing
model; action by the ordinary body-to-body sight model.  No co-location
broadcast, no objective resolve prose, no raw player input.

The resulting row is ordinary ``kind='news'`` in the body's existing sparse
mind.  That choice is the feature: gossip, reporting lines, carrier projection,
decay, scene-life recall and promotion already know how to move or hand off a
news claim, so observed scene conduct does not create a parallel history.
"""

from __future__ import annotations

import copy
import re

from world.charter_figure import figure_claim
from world.charter_identity import display_name, identity_aliases
from world.charter_mind import cap_minds
from world.spatial import (hear_level, room_of, spatial_rel_between,
                           visual_level_between)


PUBLIC_EVIDENCE_CAP = 12


def _fold(value):
    return " ".join(str(value or "").split()).casefold()


def _identity_forms(body_key, body, roles, naming):
    return {
        _fold(body_key), _fold(body.get("name")),
        _fold(display_name(body, roles, naming)),
        *(_fold(alias) for alias in identity_aliases(body, roles, naming)),
    } - {""}


def _names_body(value, forms):
    folded = _fold(value)
    return bool(folded) and any(
        folded == form or folded in form or form in folded for form in forms)


def _is_concealed(evidence, forms):
    if str(evidence.get("visibility") or "").casefold() == "concealed":
        return True
    return any(_names_body(name, forms)
               for name in (evidence.get("conceal_from") or ()))


def _observer_scene(scene, observer, place):
    """A view copy placing the unpromoted body without mutating scene.

    Charter owns this body's position until promotion, so it usually has no
    scene.positions row.  Sight still belongs to the same spatial primitive;
    adding the observer's one known position to a shallow scene copy lets that
    primitive answer without inventing a second geometry implementation.
    """
    viewed = dict(scene or {})
    viewed["positions"] = dict((scene or {}).get("positions") or {})
    viewed["positions"][observer] = str(place)
    return viewed


def body_receives_evidence(scene, body_key, body, roles, naming, evidence):
    """Whether this body receives the exact public source."""
    place = str((body or {}).get("place") or "")
    actor = str((evidence or {}).get("actor") or "")
    actor_room = str(room_of(scene or {}, actor) or "")
    if not place or not actor or not actor_room:
        return False
    forms = _identity_forms(body_key, body or {}, roles, naming)
    if _is_concealed(evidence or {}, forms):
        return False

    if evidence.get("kind") in ("speech", "communication"):
        # A private comm reaches only its named endpoint.  Otherwise sound
        # obeys the same enclosure, barrier, material, volume and distance
        # ladder the foreground perception path uses.  Exact words require
        # FULL hearing; a fragment never grants the quote or its speech act.
        if str(evidence.get("medium") or "").casefold() == "comm" \
                and _names_body(evidence.get("target"), forms):
            return True
        rel = spatial_rel_between(
            scene or {}, str(body_key), actor,
            observer_room=place, target_room=actor_room)
        return hear_level(rel, evidence.get("volume") or "normal") == "full"

    if evidence.get("kind") == "action":
        observer = f"__charter_observer__:{body_key}"
        return visual_level_between(
            _observer_scene(scene, observer, place), observer, actor) == "full"
    return False


def evidence_key(turn_id, source_id):
    return f"scene:{int(turn_id)}:{str(source_id)}"


def evidence_phrase(evidence):
    actor = " ".join(str(evidence.get("actor") or "someone").split())
    if evidence.get("kind") == "speech":
        quote = " ".join(str(evidence.get("exact_quote") or "").split())
        return f"{actor} said {quote}"[:320]
    if evidence.get("kind") == "communication":
        surface = " ".join(str(evidence.get("surface") or "communicated").split())
        return f"{actor} {surface}"[:320]
    surface = " ".join(str(evidence.get("surface") or "acted").split())
    # `observable` is normalized as a verb-first predicate phrase precisely so
    # an observer label can be prepended without changing its grammar.
    return f"{actor} {surface}"[:320]


def evidence_claim(evidence, turn_id, at_hours, place):
    """One firsthand claim, retaining only the public licensed structure."""
    source_id = str(evidence.get("source_id") or "")
    if not source_id:
        return None
    key = evidence_key(turn_id, source_id)
    actor = str(evidence.get("actor") or "")
    licensed = {
        field: copy.deepcopy(evidence[field])
        for field in (
            "kind", "actor", "target", "surface", "exact_quote",
            "speech_acts", "status", "salience")
        if field in evidence
    }
    return {
        "kind": "news", "body": key,
        "event_kind": f"figure_{evidence.get('kind') or 'conduct'}",
        "about": actor, "claim_text": evidence_phrase(evidence),
        "place": str(place or ""), "happened_at": float(at_hours),
        # Scene turns may advance while the off-screen simulation clock does
        # not.  This tie-breaker keeps the latest encountered conduct at the
        # front of Scene Life's bounded recall on a long conversation.
        "scene_turn": int(turn_id),
        "strength": 1.0, "as_of_hours": float(at_hours),
        "heard_from": None, "provenance": "witnessed_%s" % (
            evidence.get("kind") or "conduct"),
        "world_event_id": key, "source_event_id": "",
        "retellings": 0, "public_evidence": licensed,
    }


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", str(text or "").casefold()))


def resolve_target_body(charter, label, *, place=None, scene=None):
    """The one unpromoted body a Director spelling names, or None.

    The Director writes a person as whatever the prose reached for -- an
    entity id it minted, a role noun, a display name, a slug of two of the
    three words in a name -- and every ledger below this line is keyed by
    BODY KEY. Four readings, each exact in its own way, tried in order and
    never widened: an identity form (`_identity_forms`: key, name, display
    name, authored aliases); a scene entity the identity floor bound to a
    body (`charter_ref`); and a token subset (every word of the label is a
    word of exactly one body's identity forms -- "reeve_halinham" is the
    body named "Reeve Halinham Nookfeller" and nobody else). ``place``
    narrows the candidates to the bodies standing there, which is where an
    act toward somebody has to land anyway. Two bodies matching is nobody:
    an act that cannot say WHOM it means must not land on either.
    """
    label = " ".join(str(label or "").split())
    if not label:
        return None
    bodies = charter.get("bodies") or {}
    bindings = charter.get("bindings") or {}
    naming = charter.get("naming") or {}
    role_map = {}
    for post, assigned in (charter.get("watch") or {}).items():
        role_map.setdefault(str(assigned), []).append(str(post))
    candidates = {}
    for body_key, body in sorted(bodies.items()):
        if body_key in bindings:
            continue
        if place is not None and str(body.get("place") or "") != str(place):
            continue
        candidates[str(body_key)] = _identity_forms(
            body_key, body, role_map.get(body_key) or (), naming)
    if not candidates:
        return None
    folded = _fold(label)
    exact = [key for key, forms in candidates.items() if folded in forms]
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None
    # An entity the identity floor already bound to a body.
    for eid, entity in ((scene or {}).get("entities") or {}).items():
        if not isinstance(entity, dict):
            continue
        ref = entity.get("charter_ref")
        if not isinstance(ref, dict):
            continue
        spellings = {_fold(eid), _fold(entity.get("name"))} | {
            _fold(a) for a in (entity.get("aliases") or ())}
        body_key = str(ref.get("body") or "")
        if folded in spellings and body_key in candidates:
            return body_key
    words = _tokens(label)
    if not words:
        return None
    subset = [key for key, forms in candidates.items()
              if any(words <= _tokens(form) for form in forms)]
    return subset[0] if len(subset) == 1 else None


def plan_public_evidence(charter, evidence_rows, scene, turn_id):
    """READ-ONLY appraisal: what `apply_public_evidence` WOULD land.

    Mutates nothing, so it may run against the shared cached registry
    (`charter_runtime.cached_registry`) -- which is the point: the commit
    stage asks every turn whether a beat reached any Charter mind, and the
    answer is usually no (measured 2026-08-28, chat 95, 307 bodies: the
    turn's evidence pass acquired nothing, yet paid a private 41.4MB
    registry parse, ~1.1s inside the locked commit, before discovering
    that). The mutating pass consumes exactly this plan, so the two cannot
    drift.

    Returns ``{"opportunities", "acquired", "receiving", "inserts",
    "recipients"}`` where ``receiving`` is the first-reception order of
    body keys (the mutating pass creates mind rows in that order -- a body
    that receives but acquires nothing still gets its empty mind row, and
    stored-byte identity depends on the creation order) and ``inserts`` is
    ``[(body_key, subject, claim)]`` in application order.
    """
    bodies = charter.get("bodies") or {}
    bindings = charter.get("bindings") or {}
    minds = charter.get("minds") or {}
    naming = charter.get("naming") or {}
    role_map = {}
    for post, assigned in (charter.get("watch") or {}).items():
        role_map.setdefault(str(assigned), []).append(str(post))

    opportunities = acquired = 0
    # Unpromoted bodies have no individual facing/station in the scene graph;
    # for an overt source the sensory answer is therefore identical for every
    # Charter body sharing a place.  Cache that answer by source+place so a
    # thousand-person hall does not copy/re-evaluate the same scene a thousand
    # times.  Targeted concealment remains per identity and bypasses the cache.
    sensory_cache = {}
    recipients = {}
    receiving = []
    inserts = []
    # Subjects this plan already inserts per body: stands in for the live
    # `held` dict the mutating pass grows as it goes, so the duplicate-claim
    # skip sees planned insertions exactly as it would see landed ones.
    planned = {}
    clock = float(charter.get("clock_hours") or 0.0)
    for evidence in list(evidence_rows or ())[:PUBLIC_EVIDENCE_CAP]:
        if not isinstance(evidence, dict):
            continue
        for body_key, body in sorted(bodies.items()):
            if body_key in bindings:
                continue
            opportunities += 1
            roles = role_map.get(body_key) or ()
            cacheable = (str(evidence.get("visibility") or "overt").casefold()
                         != "concealed" and not evidence.get("conceal_from"))
            cache_key = (str(evidence.get("source_id") or ""),
                         str(body.get("place") or ""))
            if cacheable and cache_key in sensory_cache:
                receives = sensory_cache[cache_key]
            else:
                receives = body_receives_evidence(
                    scene, body_key, body, roles, naming, evidence)
                if cacheable:
                    sensory_cache[cache_key] = receives
            if not receives:
                continue
            recipients.setdefault(
                str(evidence.get("source_id") or ""), set()).add(str(body_key))
            held = minds.get(str(body_key)) or {}
            new = planned.get(str(body_key))
            if new is None:
                new = planned[str(body_key)] = set()
                receiving.append(str(body_key))
            claim = evidence_claim(evidence, turn_id, clock,
                                   body.get("place") or "")
            if claim is None or claim["body"] in held or claim["body"] in new:
                continue
            inserts.append((str(body_key), claim["body"], claim))
            new.add(claim["body"])
            # The same reception also refreshes the body's coarse view of the
            # figure.  This is not a second mind for the player/character: it
            # is what this Charter person believes they saw at this place.
            actor = str(evidence.get("actor") or "")
            if actor:
                inserts.append((str(body_key), actor, figure_claim({
                    "key": actor, "place": str(body.get("place") or ""),
                    "surface": {"label": actor},
                }, clock)))
                new.add(actor)
            acquired += 1
    return {"opportunities": opportunities, "acquired": acquired,
            "receiving": receiving, "inserts": inserts,
            "recipients": recipients}


def apply_public_evidence(charter, evidence_rows, scene, turn_id):
    """Land each row only in the Charter bodies that received it.

    Returns ``(charter, metrics)``.  The input is normalized state owned by the
    caller; this function mutates that copy for the same reason Charter's other
    pure reducers do, then returns it explicitly.
    """
    plan = plan_public_evidence(charter, evidence_rows, scene, turn_id)
    opportunities, acquired = plan["opportunities"], plan["acquired"]
    recipients = plan["recipients"]
    minds = charter.setdefault("minds", {})
    for body_key in plan["receiving"]:
        minds.setdefault(body_key, {})
    for body_key, subject, claim in plan["inserts"]:
        minds[body_key][subject] = claim

    charter["minds"] = cap_minds(minds)
    charter["news_keys"] = sorted({
        subject for claims in charter["minds"].values()
        for subject, claim in claims.items() if claim.get("kind") == "news"
    })
    # The utterance record is local institutional recognition, not universal
    # validity: only bodies that actually heard the exact source are named.
    from world.charter_commitment import observe_public_commitments
    from world.charter_social import update_judgments_from_minds, update_ties

    # The party a promise names, as the body key its ledgers are read by
    # (`resolve_target_body`): among the bodies that heard it, since a
    # promise made to somebody who did not hear it was made to nobody.
    targets = {}
    for evidence in evidence_rows or ():
        if not isinstance(evidence, dict) or evidence.get("kind") != "speech":
            continue
        source_id = str(evidence.get("source_id") or "")
        heard = recipients.get(source_id) or ()
        if not heard:
            continue
        listening = {"bodies": {k: v for k, v in (charter.get("bodies") or {}).items()
                                if k in heard},
                     "watch": charter.get("watch"),
                     "naming": charter.get("naming")}
        body_key = resolve_target_body(
            listening, evidence.get("target"), scene=scene)
        if body_key:
            targets[source_id] = body_key
    charter["commitments"], commitment_metrics = observe_public_commitments(
        charter.get("commitments"), evidence_rows, recipients,
        at_hours=float(charter.get("clock_hours") or 0.0), targets=targets)
    charter["judgments"], movements = update_judgments_from_minds(
        charter.get("judgments"), charter["minds"],
        politics=charter.get("politics"), norms=charter.get("social_norms"))
    # AND RELABEL IN THE BEAT IT LANDS. This is the one path where the axes
    # actually move during play -- it is where the player's own conduct enters
    # a Charter body's head -- so a betrayal witnessed on screen must be able
    # to break a bond now rather than waiting for the next offscreen window.
    # That immediacy is the whole legibility claim of the discrete tie; a
    # label that arrives four hours after the scene that earned it is a label
    # nobody can state.
    #
    # No `company` here on purpose. Co-presence is what the offscreen window
    # counts; a scene beat moves judgments and nothing else this layer reads,
    # so `movements` is the complete dirty set for this path.
    charter["ties"], tie_changes = update_ties(
        charter.get("ties"), company=None, movements=movements,
        judgments=charter["judgments"], politics=charter.get("politics"),
        served_beside=charter.get("served_beside"),
        at_hours=float(charter.get("clock_hours") or 0.0))
    return charter, {"opportunities": opportunities, "acquired": acquired,
                     "commitments_opened": int(
                         commitment_metrics.get("opened") or 0),
                     "judgments_moved": len(movements),
                     "ties_changed": len(tie_changes)}


__all__ = [
    "PUBLIC_EVIDENCE_CAP", "apply_public_evidence", "body_receives_evidence",
    "evidence_claim", "evidence_key", "evidence_phrase",
    "plan_public_evidence", "resolve_target_body",
]
