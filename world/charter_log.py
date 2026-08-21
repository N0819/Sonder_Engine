"""Reading a run: a chronicle of what happened, and what the heads believe.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §11. The event list is what
the simulation WRITES DOWN, and it is deliberately thin — a quiet month is
zero rows, which is the cost model working. That makes it a poor way to see
whether the thing is behaving, because a silent run and a broken run look
alike from the outside.

So this is the other view: a per-window trace and a set of summary statistics
that are diagnostics rather than state. NOTHING HERE IS CANON. No mind reads
it, nothing commits it, and a run behaves identically whether it is collected
or not — the trace is handed back beside the events rather than folded into
them, so there is no way for a diagnostic to become a fact a character can
learn.

The statistics worth watching, and why each one earned its place:

  * **acquaintance** — how many people the average head has an opinion about.
    Falls to nothing if decay outruns encounters, which is the shape of the
    defect that had 476 of 500 roster entries sitting at zero.
  * **contested** — bodies more than one thing is believed about. With a
    single roster this is always zero; any number above it is per-head belief
    doing the thing it was built for.
  * **hearsay share** — how much of what is believed is second-hand. Should
    be most of it in a large institution, and none of it for the handful
    actually standing posts.
"""

from __future__ import annotations

from .charter_mind import acquaintance, contested
from .charter_model import out_of_band


def window_note(charter, events, told):
    """One line of trace for a window. Pure diagnostics."""
    minds = charter.get("minds") or {}
    known = acquaintance(minds)
    return {
        "at_hours": float(charter.get("clock_hours") or 0.0),
        "events": len(events),
        "told": int(told),
        "posts_filled": len(charter.get("watch") or {}),
        "acquaintance_mean": (
            round(sum(known.values()) / len(known), 2) if known else 0.0),
        "failing": sorted(
            key for key, upkeep in (charter.get("upkeeps") or {}).items()
            if out_of_band(upkeep)),
    }


def summarize(charter, events, trace=()):
    """Everything worth knowing about a finished run, in one dict."""
    minds = charter.get("minds") or {}
    roster = charter.get("roster") or {}
    bodies = charter.get("bodies") or {}
    known = acquaintance(minds)
    disputed = contested(minds, bodies)
    hearsay = [r for r in roster.values() if r.get("heard_from")]
    kinds = {}
    for event in events or []:
        kinds[event["kind"]] = kinds.get(event["kind"], 0) + 1

    return {
        "hours": float(charter.get("clock_hours") or 0.0),
        "bodies": len(bodies),
        "posts": len(charter.get("posts") or {}),
        "rooms": len((charter.get("scene") or {}).get("rooms") or {}),
        "events": len(events or []),
        "event_kinds": dict(sorted(kinds.items())),
        "failing": sorted(
            key for key, upkeep in (charter.get("upkeeps") or {}).items()
            if out_of_band(upkeep)),
        "minds_holding_opinions": len([h for h, n in known.items() if n]),
        "acquaintance_mean": (
            round(sum(known.values()) / len(known), 2) if known else 0.0),
        "acquaintance_max": max(known.values()) if known else 0,
        "contested_bodies": len(disputed),
        "contested_sample": disputed[:5],
        "roster_entries": len(roster),
        "roster_hearsay": len(hearsay),
        "blame": dict(sorted(
            (charter.get("politics") or {}).get("blame", {}).items(),
            key=lambda kv: -kv[1])[:5]),
        "windows_traced": len(trace or ()),
    }


def chronicle(events, hours_per_day=24.0):
    """The event list as dated lines. For a human, not for a mind."""
    lines = []
    for event in events or []:
        at = float(event["at_hours"])
        stamp = f"day {int(at // hours_per_day) + 1:>3} " \
                f"{int(at % hours_per_day):02d}:00"
        detail = event.get("upkeep") or event.get("post") or ""
        extra = ""
        if event.get("starved_by"):
            extra = f"  <- starved by {event['starved_by']}"
        elif event.get("reason"):
            extra = f"  ({event['reason']})"
        elif event.get("level") is not None:
            extra = f"  level {event['level']:.2f}"
        lines.append(f"{stamp}  {event['kind']:<22}{detail}{extra}")
    return lines
