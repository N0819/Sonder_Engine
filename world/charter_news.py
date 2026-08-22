"""Things that happened, as things people can know and say.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md``. The simulation mints events
-- a condition crossing its floor, a post nobody filled, a body going down --
each stamped with a place and an hour. Until now **not one of them ever
entered anybody's head.** The news existed and nobody could hear it.

That is why a town with a healthy social layer still had only one topic. The
practices layer gave people thousands of occasions to talk (measured: 5,432
interactions across a hundred beats, none of them idle) and the only
proposition anybody could exchange was whether somebody was available and what
they were rated for. Thousands of conversations, one subject.

WITNESSING IS THE CHANNEL, and it is the one the engine already uses. From
``story/carriers.py``: *when a mechanically fired event has a non-empty public
witnessed surface, only registered characters physically at that location
acquire that surface. The report then travels because its holder travels.*
Same rule, one tier down -- a body at the place when it happens knows; nobody
else does; and it spreads only by being told.

ONE STORE, NOT TWO. A news claim lives in the same ``minds`` dict as a claim
about a person, discriminated by ``kind``. A parallel store would be the
mistake this project keeps paying for, and it would also cost the free win:
``charter_practice``'s ``tell`` and ``ask`` read whatever a head holds, so
news travels on the machinery that already exists without a line of new
plumbing.
"""

from __future__ import annotations

from .charter_mind import PERSONAL_FLOOR
from .charter_talk import co_present

#: Event kinds that have a public surface -- something a body standing there
#: could actually notice. The rest are REGISTER facts: `post_unfilled` is a
#: conclusion the institution reached in its own books, and a body in the room
#: has no way to perceive it. Getting this list wrong is a firewall leak, so it
#: is an allowlist and not a denylist.
WITNESSABLE = {
    "upkeep_out_of_band": "the state of the place itself",
    "upkeep_restored": "the state of the place itself",
    "body_unable": "somebody going down in front of you",
    "body_recovered": "somebody back on their feet",
    "post_filled_again": "somebody arriving to stand a post",
}

#: What a fresh witnessing is worth. Full: you saw it.
WITNESS_STRENGTH = 1.0

#: News fades faster than a face. You forget that the road was out before you
#: forget the man who told you.
NEWS_DECAY_PER_HOUR = 0.014

FIRSTHAND_PROVENANCE = frozenset({
    "witnessed_surface", "charter_witness", "witnessed_speech",
    "witnessed_action", "witnessed_conduct",
})


def report_key(report):
    """The Charter-mind subject for one ordinary carrier envelope.

    ``story.carriers`` and Charter used to agree on the physics but not on
    the holder: a report could enter a registered character, crowd, courier
    or artifact while an unpromoted Charter person standing beside them had
    no representation on that rail.  The objective event id is already the
    carrier network's stable identity, so prefixing it gives Charter one
    collision-proof subject without minting a second event id.
    """
    event_id = str((report or {}).get("world_event_id") or "").strip()
    return f"report:{event_id}" if event_id else ""


def _retellings(report):
    try:
        return max(0, int((report or {}).get("retellings") or 0))
    except (TypeError, ValueError):
        return 0


def _report_strength(report):
    """Confidence left after the mouths already recorded on an envelope."""
    retellings = _retellings(report)
    # Wording degradation remains story.degradation's job.  This is only the
    # coarse mind's confidence, and deliberately never raises a retelling.
    return max(PERSONAL_FLOOR, 1.0 - 0.16 * retellings)


def claim_from_report(report, at_hours):
    """Translate one legitimately acquired carrier envelope into news.

    The holder receives WHAT THE ENVELOPE SAYS, never the objective event.
    That distinction is load-bearing for lies and degraded rumours: a Charter
    mind must be just as deceivable as a full character.  Provenance and the
    retelling count survive so promotion can hand the same epistemic past to
    the full cognition tier later.
    """
    report = report if isinstance(report, dict) else {}
    key = report_key(report)
    if not key or not str(report.get("claim") or "").strip():
        return None
    provenance = str(report.get("provenance") or "told")
    told_by = str(report.get("told_by") or "").strip()
    firsthand = provenance in FIRSTHAND_PROVENANCE
    invented = provenance == "invented"
    return {
        "kind": "news",
        "body": key,
        "event_kind": str(report.get("kind") or "report"),
        # External reports need their actual, possibly wrong wording.  About
        # remains a compact subject for old readers; claim_text is authority.
        "about": str(report.get("about") or report.get("claim") or "")[:320],
        "claim_text": " ".join(str(report.get("claim") or "").split())[:320],
        "place": str(report.get("acquired_location")
                     or report.get("current_location") or ""),
        "happened_at": float(report.get("occurred_at") or at_hours or 0.0),
        "strength": _report_strength(report),
        "as_of_hours": float(at_hours or 0.0),
        "heard_from": None if firsthand or invented else (told_by or None),
        "provenance": provenance,
        "world_event_id": str(report.get("world_event_id") or ""),
        "source_event_id": str(report.get("source_event_id") or ""),
        "retellings": _retellings(report),
    }


def report_from_claim(claim, *, current_location=""):
    """Project Charter news back onto the existing physical carrier rail."""
    claim = claim if isinstance(claim, dict) else {}
    if claim.get("kind") != "news" or not claim.get("body"):
        return None
    event_id = str(claim.get("world_event_id") or "").strip()
    if not event_id:
        # Native Charter happenings predate the shared bridge.  Their stable
        # news key is still a valid report identity and never claims to be an
        # objective ``world_events`` row.
        event_id = str(claim.get("body") or "")
    text = str(claim.get("claim_text") or "").strip()
    if not text:
        text = _native_news_phrase(claim)
    place = str(current_location or claim.get("place") or "")
    provenance = str(claim.get("provenance") or (
        "witnessed_surface" if claim.get("heard_from") is None else "told"))
    return {
        "world_event_id": event_id,
        "source_event_id": str(claim.get("source_event_id") or ""),
        "claim": text,
        "kind": str(claim.get("event_kind") or "report"),
        "occurred_at": float(claim.get("happened_at") or 0.0),
        "acquired_location": place,
        "current_location": place,
        "route": [place] if place else [],
        "hops": 0,
        "retellings": _retellings({
            "retellings": claim.get("retellings")
            if claim.get("retellings") is not None
            else (1 if claim.get("heard_from") else 0)}),
        "told_by": str(claim.get("heard_from") or ""),
        "provenance": provenance,
    }


def _native_news_phrase(claim):
    about = str(claim.get("about") or "something")
    place = str(claim.get("place") or "somewhere")
    phrases = {
        "upkeep_out_of_band": f"{about} fell below its operating floor at {place}",
        "upkeep_restored": f"{about} returned to working order at {place}",
        "body_unable": f"{about} became unable to continue at {place}",
        "body_recovered": f"{about} recovered enough to continue at {place}",
        "post_filled_again": f"{about} was staffed again at {place}",
    }
    return phrases.get(str(claim.get("event_kind") or ""),
                       f"{about} changed at {place}")


def news_key(event):
    """A stable id for one happening, so two witnesses hold the SAME fact.

    Without this every witness would carry a private event and nothing could
    ever be compared, agreed on, or contradicted.
    """
    subject = (event.get("upkeep") or event.get("post")
               or event.get("body") or "")
    return f"news:{event['kind']}:{subject}@{float(event['at_hours']):.4f}"


def news_claim(event, at_hours, strength=WITNESS_STRENGTH, heard_from=None):
    return {
        "kind": "news",
        "body": news_key(event),
        "event_kind": str(event["kind"]),
        "about": str(event.get("upkeep") or event.get("post")
                     or event.get("body") or ""),
        "place": str(event.get("place") or ""),
        "happened_at": float(event["at_hours"]),
        "strength": float(strength),
        "as_of_hours": float(at_hours),
        "heard_from": heard_from,
    }


def witness(minds, bodies, events, at_hours):
    """Bodies present where something happened come to know it.

    Returns ``(minds, witnessed_count)``. Presence is the whole test: no
    timer, no broadcast, and nobody learns a thing because it is true.
    """
    seen = 0
    rooms = co_present(bodies)
    for event in events or []:
        if event.get("kind") not in WITNESSABLE:
            continue
        place = str(event.get("place") or "")
        if not place:
            continue
        key = news_key(event)
        for body_key in rooms.get(place, ()):
            held = minds.setdefault(body_key, {})
            if key in held:
                continue
            held[key] = news_claim(event, at_hours)
            seen += 1
    return minds, seen


def decay_news(minds, hours, keys=None):
    """News fading in every head. Body claims are left to `charter_mind`.

    ``keys`` is the set of news subjects currently in play, carried on the
    charter. WITHOUT IT THIS IS A FULL SCAN of every claim in every head every
    window, and a run where nothing has happened has no news to decay: five
    hundred bodies times forty-eight claims times a hundred and eighty windows
    of finding nothing, which measured as nine seconds of a seventeen-second
    month. An index over the one store, not a second copy of it -- the same
    shape as `reported`.
    """
    hours = max(0.0, float(hours))
    if keys is not None and not keys:
        return minds
    loss = NEWS_DECAY_PER_HOUR * hours
    for holder, claims in (minds or {}).items():
        held = ([s for s in keys if s in claims] if keys is not None
                else [s for s, c in claims.items() if c.get("kind") == "news"])
        for subject in held:
            claim = claims[subject]
            strength = float(claim.get("strength") or 0.0) - loss
            if strength < PERSONAL_FLOOR:
                del claims[subject]
            else:
                claim["strength"] = strength
    return minds


def news_keys_in(minds):
    """Every news subject any head currently holds. The index `decay_news`
    wants, rebuilt only when something was witnessed."""
    return {s for claims in (minds or {}).values()
            for s, c in claims.items() if c.get("kind") == "news"}


def known_news(minds, holder):
    """What one head currently knows happened, strongest first.

    The scene manager's raw material: everything this presence could bring up
    unprompted, and nothing it could not.
    """
    def scene_turn(claim):
        try:
            return int(claim.get("scene_turn") or 0)
        except (TypeError, ValueError):
            return 0

    claims = [c for c in (minds.get(str(holder)) or {}).values()
              if c.get("kind") == "news"]
    claims.sort(key=lambda c: (-float(c.get("strength") or 0.0),
                               -scene_turn(c),
                               -float(c.get("happened_at") or 0.0)))
    return claims


def spread_of(minds, key):
    """How many heads hold one piece of news, and how many heard it second-hand.

    The propagation measurement: a news front is visible as this number
    climbing over beats, which is falsifiable in a way "feels alive" is not.
    """
    holders = [c for claims in (minds or {}).values()
               for s, c in claims.items() if s == key]
    return len(holders), sum(1 for c in holders if c.get("heard_from"))
