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


def apply_public_evidence(charter, evidence_rows, scene, turn_id):
    """Land each row only in the Charter bodies that received it.

    Returns ``(charter, metrics)``.  The input is normalized state owned by the
    caller; this function mutates that copy for the same reason Charter's other
    pure reducers do, then returns it explicitly.
    """
    bodies = charter.get("bodies") or {}
    bindings = charter.get("bindings") or {}
    minds = charter.setdefault("minds", {})
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
            held = minds.setdefault(str(body_key), {})
            claim = evidence_claim(
                evidence, turn_id, float(charter.get("clock_hours") or 0.0),
                body.get("place") or "")
            if claim is None or claim["body"] in held:
                continue
            held[claim["body"]] = claim
            # The same reception also refreshes the body's coarse view of the
            # figure.  This is not a second mind for the player/character: it
            # is what this Charter person believes they saw at this place.
            actor = str(evidence.get("actor") or "")
            if actor:
                held[actor] = figure_claim({
                    "key": actor, "place": str(body.get("place") or ""),
                    "surface": {"label": actor},
                }, float(charter.get("clock_hours") or 0.0))
            acquired += 1

    charter["minds"] = cap_minds(minds)
    charter["news_keys"] = sorted({
        subject for claims in charter["minds"].values()
        for subject, claim in claims.items() if claim.get("kind") == "news"
    })
    # The utterance record is local institutional recognition, not universal
    # validity: only bodies that actually heard the exact source are named.
    from world.charter_commitment import observe_public_commitments
    from world.charter_social import update_judgments_from_minds, update_ties

    charter["commitments"], commitment_metrics = observe_public_commitments(
        charter.get("commitments"), evidence_rows, recipients,
        at_hours=float(charter.get("clock_hours") or 0.0))
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
]
