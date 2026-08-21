"""Advancing an institution through time, and the only things it writes down.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §6 and §7. This is the
path-dependent half: what can be recomputed from the clock stays in
``charter_drift``, and what BRANCHES is emitted here as an event.

TWO PROPERTIES THIS MODULE EXISTS TO HOLD, both of them testable and both of
them cheap to lose:

  * **Storage grows with incident, not with time.** A window in which nothing
    crossed a floor, nothing went unfilled and nothing was restored emits
    ZERO events. A well-run year is a handful of rows; a bad week is a
    hundred. A tick that writes "nothing happened" every window is the thing
    that makes a long story expensive, and it is the easy mistake here.
  * **Nothing learns anything.** An event is layer-1 fact in the sense
    ``world/living_world.py`` already uses: it happened, at a place, at an
    hour, before anyone asks. Who comes to know it is a separate, channelled
    question this module does not touch.

Returns events rather than committing them. Wiring these into the existing
consequence-fuse mint is deliberately NOT done here -- the prototype proves the
mechanism first, and a pure function is testable in ways a commit path is not.
"""

from __future__ import annotations

from .charter_drift import advance_level, starving_input, supply_factor
from .charter_model import normalize_charter, out_of_band
from .charter_plan import plan_watch, tended_upkeeps
from .charter_roster import decay_roster, observe


def _event(kind, at_hours, place, **payload):
    return {"kind": kind, "at_hours": round(float(at_hours), 6),
            "place": str(place or ""), **payload}


def step(charter, hours=4.0, seed=0):
    """Advance one planning window. Returns ``(charter, events)``.

    The charter is returned rather than mutated, so a caller may explore a
    window without committing to it -- which is what a rerun-from-stage or a
    checkpoint restore needs, and what a tick that mutated in place could not
    offer.
    """
    charter = normalize_charter(charter)
    hours = max(0.0, float(hours))
    at = float(charter["clock_hours"])
    events = []

    plan = plan_watch(charter, horizon_hours=hours, seed=seed)
    served = tended_upkeeps(charter, plan["watch"])

    # ONLY THE CHANGE IS AN EVENT, for posts exactly as for upkeeps. The rule
    # was written for upkeeps and not applied here, and the cost model went
    # immediately: a two-week run over one broken ship wrote 169 rows for five
    # things happening, because an unfilled post re-reported every window. A
    # post that stays unfilled for a fortnight is one fact, not eighty-four.
    #
    # `reported` carries the standing condition forward so a repair, and then
    # a second failure, produce two events rather than one or none.
    reported = {k: dict(v) for k, v in (charter.get("reported") or {}).items()}
    standing_unfilled = reported.get("post_unfilled") or {}
    standing_absent = reported.get("post_believed_filled") or {}

    now_unfilled = {e["post"]: e["reason"] for e in plan["unfilled"]}
    for entry in plan["unfilled"]:
        if standing_unfilled.get(entry["post"]) == entry["reason"]:
            continue
        events.append(_event(
            "post_unfilled", at, entry["place"],
            post=entry["post"], reason=entry["reason"],
            serves=list(entry["serves"])))
    for post_key in sorted(set(standing_unfilled) - set(now_unfilled)):
        post = charter["posts"].get(post_key) or {}
        events.append(_event(
            "post_filled_again", at, post.get("place", ""), post=post_key))

    # A post staffed from a stale roster with a body that is not in fact there
    # tends nothing and says nothing -- the charter believes it is covered.
    # Emitted because it BRANCHES (the upkeep will now drift), not because
    # anybody noticed.
    now_absent = {}
    for post_key, body_key in plan["watch"].items():
        body = charter["bodies"].get(body_key)
        if body is None or not body["available"]:
            post = charter["posts"][post_key]
            now_absent[post_key] = body_key
            if standing_absent.get(post_key) == body_key:
                continue
            events.append(_event(
                "post_believed_filled", at, post["place"],
                post=post_key, body=body_key,
                reason="absent" if body else "no_such_body"))

    # Supply is read from the levels as they stand at the START of the window,
    # for every upkeep at once. Reading them as they update would make the
    # result depend on dict iteration order -- a chain would behave one way
    # upstream-first and another downstream-first, and neither replay nor
    # checkpoint restore would be honest.
    before_levels = dict(charter["upkeeps"])

    upkeeps = {}
    for key, upkeep in charter["upkeeps"].items():
        was_down = out_of_band(upkeep)
        tended = hours if key in served else 0.0
        supply = supply_factor(upkeep, before_levels)
        after = dict(upkeep)
        after["level"] = advance_level(
            upkeep, hours, tended_hours=tended, supply=supply)
        now_down = out_of_band(after)

        # Only the CROSSING is an event. A condition that was already below
        # its floor and stays there writes nothing further -- otherwise a
        # broken thing costs a row every window forever, which is exactly the
        # storage-grows-with-time failure this module is built to avoid.
        if now_down and not was_down:
            # Name the input that starved it, when one did. A chain that
            # collapses must say WHERE, or the log records a symptom and hides
            # its cause -- the town ran out of bread is not the story, the
            # town ran out of flour is.
            starved = starving_input(upkeep, before_levels) if supply < 1.0 \
                else None
            events.append(_event(
                "upkeep_out_of_band", at + hours, after["place"],
                upkeep=key, level=round(after["level"], 6),
                floor=after["floor"], starved_by=starved))
        elif was_down and not now_down:
            events.append(_event(
                "upkeep_restored", at + hours, after["place"],
                upkeep=key, level=round(after["level"], 6)))
        upkeeps[key] = after

    # STANDING A POST IS AN OBSERVATION, and without this rule the whole
    # institution starves: roster claims decay, every one of them falls under
    # TRUST_FLOOR at the same hour, the charter stops staking posts on anybody
    # and a fully healthy crew watches its ship fail. Measured on the first
    # run of this module: reactor_thermal crossed its floor at hour 240 with
    # six able bodies aboard and nothing wrong.
    #
    # The rule is also the right one in the fiction, which is why it is a fix
    # rather than a fudge: rosters are kept current by people turning up. A
    # body that stands its watch is seen standing it, so the charter's claim
    # about it is refreshed from what was actually there. A body that never
    # appears decays quietly out of the roster, which IS the "he transferred
    # out two months ago" case arriving on its own.
    #
    # Scope limit, stated rather than hidden: only being ON a post counts as
    # being seen. A crew that passes each other in a corridor all day would
    # also keep a roster current, and this prototype has no co-presence to
    # read. So it forgets an idle body faster than a real institution would.
    roster = decay_roster(charter["roster"], hours)
    for post_key, body_key in plan["watch"].items():
        body = charter["bodies"].get(body_key)
        if body is not None and body["available"]:
            roster = observe(roster, body, at + hours)

    after_charter = dict(charter)
    after_charter["upkeeps"] = upkeeps
    after_charter["roster"] = roster
    after_charter["clock_hours"] = at + hours
    after_charter["watch"] = dict(plan["watch"])
    after_charter["reported"] = {
        "post_unfilled": now_unfilled,
        "post_believed_filled": now_absent,
    }
    return after_charter, events


def run(charter, hours, window=4.0, seed=0):
    """Advance many windows. Returns ``(charter, events)``.

    The shape a test drives ten thousand simulated hours through, and the
    shape an out-of-band job would use to catch a world up to the wall clock
    at re-contact.
    """
    charter = normalize_charter(charter)
    remaining = max(0.0, float(hours))
    window = max(1e-6, float(window))
    events = []
    index = 0
    while remaining > 0.0:
        span = min(window, remaining)
        # The seed advances with the window so successive windows are not
        # identical draws, while the whole run stays a pure function of the
        # caller's seed.
        charter, produced = step(charter, hours=span, seed=int(seed) + index)
        events.extend(produced)
        remaining -= span
        index += 1
    return charter, events
