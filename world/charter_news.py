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
    claims = [c for c in (minds.get(str(holder)) or {}).values()
              if c.get("kind") == "news"]
    claims.sort(key=lambda c: (-float(c.get("strength") or 0.0),
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
