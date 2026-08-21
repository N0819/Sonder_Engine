"""What time does to an upkeep, and what a tended post gives back.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §6, the recomputable half.
Everything here is a pure function of (level, hours, whether it was tended), so
an unattended stretch needs no history and no stored tick -- the same property
that lets ``world/routines.py`` cost nothing over a hundred quiet turns.

The path-dependent half is NOT here. Whether a condition crossed its floor,
and what that caused, is a branch: those commit, and they live in
``charter_run``. This module only answers "where would it stand".
"""

from __future__ import annotations

from .charter_model import LEVEL_MAX, LEVEL_MIN, out_of_band


def supply_factor(upkeep, upkeeps):
    """How much of its service rate this upkeep's inputs actually permit.

    The weakest input governs, not the average: a chain is as strong as its
    thinnest link, and averaging would let an abundant input paper over an
    exhausted one -- which is the whole failure mode a supply chain has.
    Returns 1.0 for an upkeep that draws on nothing.
    """
    levels = [float((upkeeps or {}).get(key, {}).get("level", 0.0))
              for key in (upkeep.get("depends_on") or [])]
    return min(levels) if levels else 1.0


def starving_input(upkeep, upkeeps):
    """Which input is holding this upkeep back, or ``None``.

    Diagnostics, so a chain that collapses says WHERE. An author reading a
    town that ran out of bread needs to be told it ran out of flour, or the
    event log records a symptom and hides its cause.
    """
    worst, worst_level = None, 1.0
    for key in (upkeep.get("depends_on") or []):
        level = float((upkeeps or {}).get(key, {}).get("level", 0.0))
        if level < worst_level:
            worst, worst_level = key, level
    return worst


def advance_level(upkeep, hours, tended_hours=0.0, supply=1.0):
    """The level after ``hours``, of which ``tended_hours`` had a body on it.

    Drift and service are both linear per hour and applied over their own
    spans, so a post filled for half a window neither fully holds nor fully
    fails -- which is the ordinary case once a charter is short-handed and
    splitting somebody across two posts.

    ``supply`` scales service only. Drift is what the world does and no input
    shortage slows it down; a shortage means the tending gives back less, not
    that the condition stops decaying. That asymmetry is what makes a starved
    chain collapse rather than stall.
    """
    hours = max(0.0, float(hours))
    tended = max(0.0, min(hours, float(tended_hours)))
    untended = hours - tended
    supply = max(0.0, min(1.0, float(supply)))

    level = float(upkeep["level"])
    level -= float(upkeep["drift_per_hour"]) * untended
    # A tended hour still drifts; service is what it gives back on top, so an
    # upkeep whose drift outruns one body's service degrades even when the
    # post is filled. That is how an institution can be doing everything right
    # and still be losing, which is a state worth being able to represent.
    level -= float(upkeep["drift_per_hour"]) * tended
    level += float(upkeep["service_per_hour"]) * tended * supply
    return max(LEVEL_MIN, min(LEVEL_MAX, level))


def hours_until_floor(upkeep):
    """How long until this upkeep crosses its floor, untended.

    ``None`` when it never will -- no drift, or already below. Used to rank
    urgency, and to let a caller step straight to the next thing that actually
    happens instead of sampling time it does not need to look at.
    """
    if out_of_band(upkeep):
        return 0.0
    drift = float(upkeep["drift_per_hour"])
    if drift <= 0.0:
        return None
    return (float(upkeep["level"]) - float(upkeep["floor"])) / drift


def urgency(upkeep, rank, horizon_hours):
    """How loudly this upkeep is asking for a body, within ``horizon_hours``.

    Two terms, and the ordering between them is deliberate: an institution
    abandons in priority order, so rank dominates, and time-to-floor only
    orders things of equal rank. A charter that let a cheap urgent upkeep
    outbid its most important one would not read as an institution at all --
    it would read as a task queue.
    """
    remaining = hours_until_floor(upkeep)
    if remaining is None:
        nearness = 0.0
    elif remaining <= 0.0:
        nearness = 1.0
    else:
        nearness = max(0.0, 1.0 - (remaining / max(1e-9, horizon_hours)))
    return (-int(rank), nearness)
