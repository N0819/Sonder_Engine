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

    THE WHOLE RECORD TRAVELS, not a rebuilt one. The first version of this
    function reconstructed the claim from the three body-claim fields, which
    quietly destroyed every OTHER kind on retell: a news claim arrived
    stripped of ``kind``/``event_kind``/``place``/``happened_at`` — a
    body-claim asserting ``believed_available: False`` about a pseudo-body
    named ``news:…`` — so a second-hand fact could never surface in
    ``known_news`` or a scene ledger's ``can_bring_up``. "News travels on
    the practice machinery for free" was half-true: it travelled as an
    unintelligible token. Found by calling the consumer, which no test did.
    """
    told = (minds.get(str(speaker)) or {}).get(str(subject))
    if not told:
        return False
    return hear_claim(minds, listener, told, retention, regard,
                      heard_from=speaker)


def hear_claim(minds, listener, claim, retention, regard=1.0,
               heard_from=None):
    """One claim arriving in one head, whoever is doing the telling.

    THE ONLY UPTAKE DOOR. ``hear`` routes through it for body-to-body talk;
    an authored telling — a voiced presence, the player, a major character
    speaking to a background body — lands through the same door with the
    same rules: thinned by retention, scaled by the listener's regard for
    the teller, refused below the floor, and never overwriting a stronger
    holding. A second uptake path with its own arithmetic is how the two
    authors would drift apart.
    """
    subject = str(claim.get("body") or "")
    if not subject:
        return False
    arriving = float(claim.get("strength") or 0.0) * float(retention) \
        * float(regard)
    if arriving < PERSONAL_FLOOR:
        return False
    news_retellings = None
    if claim.get("kind") == "news":
        from world.degradation import degrade, is_exhausted

        try:
            news_retellings = max(0, int(claim.get("retellings") or 0)) + 1
        except (TypeError, ValueError):
            news_retellings = 1
        if is_exhausted(news_retellings):
            return False
    held = minds.setdefault(str(listener), {})
    current = held.get(subject)
    if current is not None \
            and float(current.get("strength") or 0.0) >= arriving:
        return False
    record = dict(claim)
    record["strength"] = arriving
    record["heard_from"] = str(heard_from) if heard_from else None
    if news_retellings is not None:
        record["retellings"] = news_retellings
        # A firsthand observation may retain an exact quote and typed
        # speech-act spans.  A retelling retains WHAT THE TELLER SAID (the
        # degraded claim_text below), not a hidden pristine transcript one
        # careless consumer could quote as if the listener had been there.
        # Keeping only the act kinds preserves useful direction -- request vs
        # offer -- without preserving words or named roles degradation has
        # already begun to subtract.
        public = record.get("public_evidence")
        if isinstance(public, dict):
            if str(public.get("kind") or "") == "speech" \
                    and str(public.get("exact_quote") or "").strip():
                actor = " ".join(str(
                    public.get("actor") or record.get("about") or "someone"
                ).split())
                quote = str(public.get("exact_quote") or "").strip()
                if len(quote) >= 2 and quote[0] in '\"\'“' \
                        and quote[-1] in '\"\'”':
                    quote = quote[1:-1].strip()
                # Still the wording the teller passed, but no longer stored
                # as a transcript the listener personally witnessed.
                record["claim_text"] = f"{actor} was reported saying {quote}"
            kinds = [
                str(frame.get("kind") or "other")
                for frame in (public.get("speech_acts") or [])
                if isinstance(frame, dict)
            ][:4]
            record["public_evidence"] = {
                "kind": str(public.get("kind") or ""),
                **({"speech_act_kinds": kinds} if kinds else {}),
                "secondhand": True,
            }
        if str(record.get("claim_text") or "").strip():
            # Counts can be safely recognized without guessing identities.
            # Named people/places are removed later by the shared carrier
            # renderer, whose caller owns the authoritative rosters.
            record["claim_text"] = degrade(
                record["claim_text"], news_retellings)
    held[subject] = record
    return True


def decay_minds(minds, hours):
    """Time passing in every head, and the weakest opinions falling away.

    News claims are decayed by ``charter_news.decay_news`` and ONLY there —
    its docstring already promised body claims to this module, but this
    module was decaying everything, so news actually faded at the sum of two
    rates and ``NEWS_DECAY_PER_HOUR`` was not the news decay rate. An
    authored rate that does not mean what it says fails silently; each store
    now has exactly one decayer. The cap still counts every kind, because a
    head's capacity does not care what the opinions are about.
    """
    hours = max(0.0, float(hours))
    loss = PERSONAL_DECAY_PER_HOUR * hours
    out = {}
    for holder, claims in (minds or {}).items():
        kept = {}
        for subject, claim in claims.items():
            if claim.get("kind") == "news":
                kept[subject] = dict(claim)
                continue
            strength = float(claim.get("strength") or 0.0) - loss
            if strength < PERSONAL_FLOOR:
                continue
            record = dict(claim)
            record["strength"] = strength
            kept[subject] = record
        out[holder] = kept
    return cap_minds(out)


def cap_minds(minds):
    """The carry limit, enforced wherever a window's additions end.

    Decay used to be the only place the cap ran, which held while heads
    only gained claims slowly: witnessing, sighting and talk all add claims
    AFTER decay, and once the population circulates (`charter_move.errands`)
    a body can meet more people in one window than decay had capped for —
    measured, a head at 49 of 48. The weakest fall away, whatever their
    kind: capacity does not care what the opinions are about.
    """
    out = {}
    for holder, claims in (minds or {}).items():
        if len(claims) > RECALL_CAP:
            ordered = sorted(
                claims.items(),
                key=lambda kv: (-float(kv[1].get("strength") or 0.0), kv[0]))
            claims = dict(ordered[:RECALL_CAP])
        out[holder] = claims
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
