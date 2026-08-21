"""What each body believes about the others — one belief set per head.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §5. Until now there was a
single institutional roster, and the limit was structural: with one belief set
there is no way for A to believe something B does not, so nothing could be
concealed, disputed, or wrong in one place and right in another. That is most
of what makes an institution interesting, and none of it was available.

THE SHAPE, and why it is not a parallel store. The charter keeps its own
roster exactly as before — an institution is an agent and holds beliefs like
anyone. What is added is ``minds``: the same claim record, held per body,
about the bodies they have actually encountered. The charter's roster is not
derived from the minds and the minds are not derived from it; they are
different agents' beliefs about a shared world, which is the engine's whole
premise rather than a duplication of it.

SPARSE BY CONSTRUCTION. A body holds claims only about people it has met, and
never more than ``RECALL_CAP`` of them. Five hundred heads times five hundred
subjects would be 250,000 claims and mostly lies about strangers; a bounded
acquaintance is both cheaper and truer. Forgetting the weakest is the
garbage collector and the realism in one rule.
"""

from __future__ import annotations

#: Claims one head keeps. Past this the weakest is dropped: a body that has
#: met three hundred people does not carry three hundred opinions, and an
#: unbounded mind is the thing that would make this package quadratic.
RECALL_CAP = 48

#: What a claim loses per hour in one head. Faster than the institution's own
#: roster decays, because a person forgets a face sooner than a register does.
PERSONAL_DECAY_PER_HOUR = 0.010

#: Below this a body no longer holds an opinion at all and drops it.
PERSONAL_FLOOR = 0.08


def normalize_minds(stored):
    """``{holder: {subject: claim}}`` from any shape."""
    out = {}
    for holder, claims in (stored or {}).items():
        if not isinstance(claims, dict):
            continue
        kept = {}
        for subject, claim in claims.items():
            if isinstance(claim, dict):
                kept[str(subject)] = dict(claim)
        out[str(holder)] = kept
    return out


def claim_from(body, at_hours, strength=1.0, heard_from=None):
    return {
        "body": str(body["key"]),
        "competence": dict(body.get("competence") or {}),
        "believed_available": bool(body.get("available")),
        "strength": float(strength),
        "as_of_hours": float(at_hours),
        "heard_from": heard_from,
    }


def see(minds, holder, body, at_hours):
    """``holder`` lays eyes on ``body``. First-hand, so full strength.

    The only way a claim enters a head accurate. Everything else is somebody
    telling you, and that arrives thinner.
    """
    held = minds.setdefault(str(holder), {})
    held[str(body["key"])] = claim_from(body, at_hours)
    return minds


def hear(minds, listener, speaker, subject, retention, regard=1.0):
    """``speaker`` tells ``listener`` what it believes about ``subject``.

    Returns True when the listener actually took it on. A listener keeps what
    it already holds if that is stronger — so a rumour cannot overwrite a
    seeing, and two heads cannot talk a claim into certainty between them by
    passing it back and forth.
    """
    told = (minds.get(str(speaker)) or {}).get(str(subject))
    if not told:
        return False
    arriving = float(told.get("strength") or 0.0) * float(retention) \
        * float(regard)
    if arriving < PERSONAL_FLOOR:
        return False
    held = minds.setdefault(str(listener), {})
    current = held.get(str(subject))
    if current is not None \
            and float(current.get("strength") or 0.0) >= arriving:
        return False
    held[str(subject)] = {
        "body": str(subject),
        "competence": dict(told.get("competence") or {}),
        "believed_available": bool(told.get("believed_available")),
        "strength": arriving,
        "as_of_hours": float(told.get("as_of_hours") or 0.0),
        "heard_from": str(speaker),
    }
    return True


def decay_minds(minds, hours):
    """Time passing in every head, and the weakest opinions falling away."""
    hours = max(0.0, float(hours))
    loss = PERSONAL_DECAY_PER_HOUR * hours
    out = {}
    for holder, claims in (minds or {}).items():
        kept = {}
        for subject, claim in claims.items():
            strength = float(claim.get("strength") or 0.0) - loss
            if strength < PERSONAL_FLOOR:
                continue
            record = dict(claim)
            record["strength"] = strength
            kept[subject] = record
        if len(kept) > RECALL_CAP:
            ordered = sorted(kept.items(),
                             key=lambda kv: (-float(kv[1]["strength"]), kv[0]))
            kept = dict(ordered[:RECALL_CAP])
        out[holder] = kept
    return out


def believes(minds, holder, subject):
    return (minds.get(str(holder)) or {}).get(str(subject))


def acquaintance(minds):
    """``{holder: how many people it currently holds an opinion about}``."""
    return {holder: len(claims) for holder, claims in (minds or {}).items()}


def divergence(minds, subject):
    """How many DIFFERENT things are believed about one body, and by how many.

    The measurable payoff of per-head belief: with one roster this is always
    1, and any number above it is a fact the institution does not agree with
    itself about. Keyed on availability and competence, because those are the
    two things a claim asserts and the two a planner acts on.
    """
    tally = {}
    for holder, claims in (minds or {}).items():
        claim = claims.get(str(subject))
        if not claim:
            continue
        key = (bool(claim.get("believed_available")),
               tuple(sorted((claim.get("competence") or {}).items())))
        tally[key] = tally.get(key, 0) + 1
    return tally


def contested(minds, bodies):
    """Bodies more than one thing is currently believed about."""
    return sorted(key for key in (bodies or {})
                  if len(divergence(minds, key)) > 1)
