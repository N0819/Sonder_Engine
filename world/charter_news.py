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
from .charter_model import out_of_band
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
    "incident": "an authored physical change at the place",
    "stock_low": "visible scarcity at a store or market",
    "stock_empty": "an empty store or market",
    "stock_restored": "supplies returning to ordinary levels",
    "stock_surplus": "an unusually well-stocked store or market",
    "goods_exchanged": "goods visibly changing hands",
    "institution_order_issued": "an order publicly issued at a post",
    "institution_order_executed": "an order visibly carried out",
    "institution_order_failed": "an attempted order visibly failing",
    "commitment_fulfilled": "a publicly witnessed fulfilment",
    "commitment_disputed": "a public dispute over an undertaking",
    "commitment_released": "a public release from an undertaking",
    "commitment_repudiated": "a public repudiation of an undertaking",
    "commitment_defaulted": "a publicly established default",
    "commitment_transferred": "a public transfer of an undertaking",
    "report_confirmed": "a report publicly confirmed",
    "report_refuted": "a report publicly refuted",
    "aid_given": "aid visibly given",
    "harm_done": "harm visibly done",
    # A speech act between two co-present bodies is heard by the room. Same
    # rule `story/carriers.py` holds one tier up, and the same one `aid_given`
    # was admitted under. What makes it legitimate is that the payload carries
    # only what a bystander perceives -- who spoke, whom they spoke to, where
    # -- and NOTHING from the institution's blame register. A payload field
    # naming the blame count, or a surface phrase built from one, would hand
    # the character tier the register's own conclusion, because
    # `charter_runtime._scheduled_row` puts a WITNESSABLE kind's surface onto
    # the objective carrier rail.
    "accusation": "an accusation made aloud",
    "apology": "a public reconciliation",
}

#: Claims a body can settle by LOOKING, and what each one asserts about the
#: place. A holder standing where the rumour named compares the assertion with
#: `out_of_band` and comes to a view about whoever told it.
#:
#: Only the condition of a PLACE is checkable. A body's own state is not
#: something a bystander reads off a room, and the institution's register is
#: not in the room at all -- so `post_unfilled` and the commitment kinds are
#: absent from this map for the same reason they are absent from WITNESSABLE.
CHECKABLE = {
    "upkeep_out_of_band": True,
    "upkeep_restored": False,
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


def charter_hours_of(seconds, anchor):
    """A simulation-clock instant on one charter's own hour clock.

    TWO CLOCKS, ONE FIELD. ``world_events.occurred_at`` counts simulation
    SECONDS from the story's opening (negative before it); a charter's
    ``clock_hours`` counts HOURS from the start of its own prehistory. A
    carrier envelope crossing from the first into a mind kept on the second
    used to land its ``occurred_at`` in ``happened_at`` unconverted, so every
    piece of imported news was stamped hundreds of thousands of hours ago --
    measured, Harrowmere playtest: ``hours_ago`` 1,728,720 on news of a
    market that ran out twenty days earlier. ``anchor`` is the pair the
    registry keeps per charter, ``{"clock_hours", "elapsed_seconds"}``: the
    charter hour that corresponds to that many simulation seconds. Absent,
    the number passes through as before.
    """
    if not isinstance(anchor, dict):
        return float(seconds)
    try:
        clock = float(anchor.get("clock_hours"))
        elapsed = float(anchor.get("elapsed_seconds"))
    except (TypeError, ValueError):
        return float(seconds)
    return clock - (elapsed - float(seconds)) / 3600.0


def sim_seconds_of(hours, anchor):
    """The inverse of ``charter_hours_of``: a charter hour as simulation
    seconds, for news projected back onto the physical carrier rail."""
    if not isinstance(anchor, dict):
        return float(hours)
    try:
        clock = float(anchor.get("clock_hours"))
        elapsed = float(anchor.get("elapsed_seconds"))
    except (TypeError, ValueError):
        return float(hours)
    return elapsed - (clock - float(hours)) * 3600.0


def claim_from_report(report, at_hours, anchor=None):
    """Translate one legitimately acquired carrier envelope into news.

    The holder receives WHAT THE ENVELOPE SAYS, never the objective event.
    That distinction is load-bearing for lies and degraded rumours: a Charter
    mind must be just as deceivable as a full character.  Provenance and the
    retelling count survive so promotion can hand the same epistemic past to
    the full cognition tier later.

    ``anchor`` converts the envelope's ``occurred_at`` (simulation seconds)
    onto the charter's hour clock -- see ``charter_hours_of``.
    """
    report = report if isinstance(report, dict) else {}
    key = report_key(report)
    if not key or not str(report.get("claim") or "").strip():
        return None
    provenance = str(report.get("provenance") or "told")
    told_by = str(report.get("told_by") or "").strip()
    firsthand = provenance in FIRSTHAND_PROVENANCE
    invented = provenance == "invented"
    occurred = report.get("occurred_at")
    if occurred is None or occurred == "":
        happened_at = float(at_hours or 0.0)
    else:
        happened_at = charter_hours_of(float(occurred), anchor)
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
        "happened_at": happened_at,
        "strength": _report_strength(report),
        "as_of_hours": float(at_hours or 0.0),
        "heard_from": None if firsthand or invented else (told_by or None),
        "provenance": provenance,
        "world_event_id": str(report.get("world_event_id") or ""),
        "source_event_id": str(report.get("source_event_id") or ""),
        "retellings": _retellings(report),
    }


def report_from_claim(claim, *, current_location="", anchor=None):
    """Project Charter news back onto the existing physical carrier rail.

    ``anchor`` puts ``happened_at`` (charter hours) back into the rail's
    simulation seconds -- see ``charter_hours_of``."""
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
        "occurred_at": sim_seconds_of(
            float(claim.get("happened_at") or 0.0), anchor),
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
    toward = str(claim.get("toward") or "")
    phrases = {
        "upkeep_out_of_band": f"{about} fell below its operating floor at {place}",
        "upkeep_restored": f"{about} returned to working order at {place}",
        "body_unable": f"{about} became unable to continue at {place}",
        "body_recovered": f"{about} recovered enough to continue at {place}",
        "post_filled_again": f"{about} was staffed again at {place}",
        # WHOM, not only who. A witness standing there saw which body the act
        # was directed at; dropping the target left every retelling of an act
        # between two people as "somebody did something at the dock".
        "aid_given": f"{about} gave aid to {toward} at {place}"
                     if toward else f"{about} gave aid at {place}",
        "accusation": f"{about} accused {toward} at {place}"
                      if toward else f"{about} made an accusation at {place}",
        "apology": f"{about} made peace with {toward} at {place}"
                   if toward else f"{about} made peace at {place}",
        "report_confirmed": f"what {about} said about {place} was borne out",
        "report_refuted": f"what {about} said about {place} was not so",
    }
    return phrases.get(str(claim.get("event_kind") or ""),
                       f"{about} changed at {place}")


def news_key(event):
    """A stable id for one happening, so two witnesses hold the SAME fact.

    Without this every witness would carry a private event and nothing could
    ever be compared, agreed on, or contradicted.
    """
    subject = (event.get("upkeep") or event.get("post")
               or event.get("body") or event.get("commitment_id")
               or event.get("order_id") or event.get("good")
               or event.get("holder") or event.get("actor") or "")
    return f"news:{event['kind']}:{subject}@{float(event['at_hours']):.4f}"


def news_claim(event, at_hours, strength=WITNESS_STRENGTH, heard_from=None):
    return {
        "kind": "news",
        "body": news_key(event),
        "event_kind": str(event["kind"]),
        "about": str(event.get("upkeep") or event.get("post")
                     or event.get("body") or event.get("actor")
                     or event.get("by") or event.get("holder")
                     or event.get("commitment_id")
                     or event.get("order_id") or event.get("good") or ""),
        "actor": str(event.get("actor") or event.get("by")
                     or event.get("seller") or event.get("holder") or ""),
        # WHOM IT WAS DIRECTED AT. This dict is FIXED -- every payload key
        # not named here is silently dropped -- which is why the existing
        # `aid_given` event set `subject` and no witness ever received it.
        # Carrying it subtracts nothing: a body standing in the room saw who
        # was helped, or accused, as plainly as it saw who acted.
        "toward": str(event.get("subject") or ""),
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


def check_reports(minds, bodies, upkeeps, at_hours, keys=None):
    """A body standing where a rumour said something, checking the rumour.

    Returns ``(minds, checks)``. This is the only ordinary-evidence source in
    the package that is not an institutional failure, and it exists because
    `report_confirmed`/`report_refuted` shipped with judgment weights
    (`charter_social.DEFAULT_SIGNALS`), a WITNESSABLE entry, runtime phrasing
    and NO PRODUCER ANYWHERE IN THE REPOSITORY -- three quarters of a feature,
    exactly the shape `aid_given` was found in. Measured before this landed: a
    healthy simulated YEAR of the 40-body `twin_towns` charter emitted 0
    events and left 0 heads holding a judgment, while depositing 6,742
    experience rows. The people were living and none of it was evidence.

    THE HOLDER'S OWN, END TO END. Everything read here belongs to the head
    drawing the conclusion: a claim it holds, whom that claim says it heard it
    from, and the condition of the place its own feet are standing in -- the
    same channel `charter_feel.advance_feel` appraises a window from. Nothing
    is read out of the teller's head, and no event is minted, so the
    conclusion exists only in the head that reached it. That its holder may
    later TELL somebody, and that the listener then judges the teller at
    `hearsay_weight`, is the uptake machinery already built, not a second
    channel.

    INFERENCE IS THE PRODUCT. What this builds is a body concluding that its
    informant was wrong, from what it was told set against what it can see;
    the answer to that is never to make the body conclude less.
    """
    checks = 0
    if keys is not None and not keys:
        return minds, checks
    for holder, claims in (minds or {}).items():
        if not isinstance(claims, dict):
            continue
        place = str(((bodies or {}).get(holder) or {}).get("place") or "")
        if not place:
            continue
        # THE SAME INDEX `decay_news` TAKES, and for the same measured
        # reason: a full scan of every claim in every head every window cost
        # nine seconds of a seventeen-second month.
        held = ([s for s in keys if s in claims] if keys is not None
                else list(claims))
        for subject in held:
            claim = claims.get(subject)
            if not isinstance(claim, dict) or claim.get("kind") != "news":
                continue
            teller = str(claim.get("heard_from") or "")
            # A claim with no teller has nobody to be right or wrong about.
            # Firsthand is not evidence about anyone; it is just what you saw.
            if not teller or teller == str(holder):
                continue
            asserted = CHECKABLE.get(str(claim.get("event_kind") or ""))
            if asserted is None:
                continue
            upkeep = (upkeeps or {}).get(str(claim.get("about") or ""))
            if not isinstance(upkeep, dict):
                continue
            # CO-LOCATION IS THE WHOLE TEST, as it is for `witness`. A body
            # elsewhere is not looking at the thing and settles nothing.
            if str(upkeep.get("place") or "") != place:
                continue
            key = f"check:{subject}:{teller}"
            # Idempotent on the same rumour from the same mouth, exactly as
            # `witness` is on the same happening: standing there twice is one
            # conclusion, not two.
            if key in claims:
                continue
            try:
                actual = bool(out_of_band(upkeep))
            except (KeyError, TypeError, ValueError):
                continue
            claims[key] = {
                "kind": "news",
                "body": key,
                "event_kind": ("report_confirmed" if actual is bool(asserted)
                               else "report_refuted"),
                # Both name the TELLER. What the holder now holds is a fact
                # about the person who told it, not about the road.
                "about": teller,
                "actor": teller,
                "toward": "",
                "place": place,
                "happened_at": float(at_hours),
                # You looked at it yourself, so it is firsthand and full
                # strength -- and it fades on the ordinary news curve like
                # anything else in this store.
                "strength": WITNESS_STRENGTH,
                "as_of_hours": float(at_hours),
                "heard_from": None,
                "checked": subject,
            }
            checks += 1
    return minds, checks


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
