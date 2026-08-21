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

from .charter_feel import normalize_feel, overloaded_bodies
from .charter_mind import acquaintance, contested, divergence
from .charter_needs import mood, pressure
from .charter_news import known_news
from .charter_feel import strain_of
from .charter_model import out_of_band
from .charter_temper import temperament_of


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
        # SPARSENESS IS THE HEALTH SIGNAL here: a quiet institution feels
        # nothing, so `feeling_bodies` at zero after a quiet month is the
        # cost model working, and nonzero after one is a leak.
        "feeling_bodies": len(normalize_feel(charter.get("feel"))),
        "overloaded_bodies": overloaded_bodies(charter.get("feel")),
        "windows_traced": len(trace or ()),
    }


def life_of(body_key, charter, events, trace=(), hours_per_day=24.0):
    """One body's whole record: where it went, what it stood, what it knows,
    what is believed about it, and what it was blamed for.

    THE VIEW A SIMULATION OWES ITS AUTHOR. A thousand bodies producing six
    events is the cost model working correctly and it is also unreadable — the
    interesting thing is never in the event log, because the event log only
    holds what BRANCHED. Everything below is reconstructed from state instead,
    which is why it costs nothing to not ask for it.

    Diagnostics, like everything else here: nothing reads this, and no mind
    receives it.
    """
    key = str(body_key)
    body = (charter.get("bodies") or {}).get(key) or {}
    minds = charter.get("minds") or {}
    politics = charter.get("politics") or {}
    needs = (charter.get("needs") or {}).get(key) or {}

    held = minds.get(key) or {}
    about = {holder: claims[key] for holder, claims in minds.items()
             if key in claims and holder != key}
    views = divergence(minds, key)

    return {
        "body": key,
        "place": body.get("place"),
        "competence": dict(body.get("competence") or {}),
        "available": bool(body.get("available", True)),
        "rooms_travelled": int((charter.get("travelled") or {}).get(key, 0)),
        "posts_held": sorted(
            post for post, who in (charter.get("watch") or {}).items()
            if who == key),
        "needs": {name: round(float(n["level"]), 3)
                  for name, n in needs.items()},
        "knows_about": len(held),
        "known_by": len(about),
        "believed_available_by": sorted(
            {holder for holder, claim in about.items()
             if claim.get("believed_available")}),
        "believed_absent_by": sorted(
            {holder for holder, claim in about.items()
             if not claim.get("believed_available")}),
        "contested": len(views) > 1,
        "register": (charter.get("roster") or {}).get(key),
        "blamed": int((politics.get("blame") or {}).get(key, 0)),
        "pressure": pressure(needs),
        # Windows actually stood, per post -- the shape of this body's
        # working life, and the evidence a promotion deliberates a project
        # from.
        "stood": dict((charter.get("stood") or {}).get(key) or {}),
        # The engine's own affect state (`mind/psychology_runtime` shapes),
        # or empty dicts for a body currently feeling nothing.
        "feel": normalize_feel(charter.get("feel")).get(key) or {},
        "temperament": temperament_of(dict(body, key=key)),
        # Reported, never acted on -- see `charter_needs.mood`.
        "mood": mood(
            needs,
            blamed=int((politics.get("blame") or {}).get(key, 0)),
            regard_of_others=[
                w for (listener, speaker), w in (
                    politics.get("regard") or {}).items() if speaker == key]),
        "regarded_by": {
            speaker: round(float(weight), 3)
            for (listener, speaker), weight in (
                politics.get("regard") or {}).items()
            if listener == key},
        "events": chronicle(
            [e for e in (events or [])
             if e.get("body") == key
             or key in (e.get("bodies") or ())],
            hours_per_day=hours_per_day),
    }


def scene_ledger(charter, place, events=(), hours_per_day=24.0):
    """Everything a scene manager could riff from, for one place, per presence.

    THE SHAPE THIS OWES ITS CALLER. `docs/design/BACKGROUND_LIFE_DESIGN.md`
    voices extras in a room, and `agents/background.py` says outright what it
    has to work with today: *no memory, no mind-models, no relationships, no
    persistent psychology*, plus a `sketch` that is "replayed self-description,
    not remembered psychology." This is the missing half — a presence with a
    past, scoped to what that presence may legitimately have.

    PER PRESENCE, NOT PER SCENE, and that is the firewall doing its job.
    Every field under `presences` is derived from that body's OWN state: its
    needs, its own claims, its own regard, the news it personally witnessed or
    was told. The institution's register is absent — that is the charter's
    belief, not this person's. Another body's interior is absent. What the
    place objectively is appears only under `place`, for the Director staging
    it, never inside a presence's slice.

    AND IT IS SELECTED, NOT DUMPED. `can_bring_up` is capped, because handing
    a cheap model everything a body knows is how chat 78's wardrobe got
    transposed into a diff: a payload large enough to restate gets restated.
    Three things somebody could plausibly raise beats forty they could not.
    """
    place = str(place)
    bodies = charter.get("bodies") or {}
    minds = charter.get("minds") or {}
    politics = charter.get("politics") or {}
    regard = politics.get("regard") or {}
    blame = politics.get("blame") or {}
    heard_blame = charter.get("heard_blame") or {}
    needs = charter.get("needs") or {}
    feel = charter.get("feel") or {}
    strains = strain_of(feel)
    watch = charter.get("watch") or {}
    posts = charter.get("posts") or {}

    here = sorted(k for k, b in bodies.items()
                  if str(b.get("place") or "") == place)
    present = set(here)

    presences = {}
    for key in here:
        body = bodies[key]
        held_needs = needs.get(key) or {}
        # What this body could raise: its news, strongest first, then the
        # people here it has an opinion about. Capped hard.
        news = [
            {"what": n["event_kind"], "about": n["about"],
             "where": n["place"], "hours_ago": round(
                 float(charter.get("clock_hours") or 0.0)
                 - float(n["happened_at"]), 1),
             "firsthand": n.get("heard_from") is None,
             "from": n.get("heard_from")}
            for n in known_news(minds, key)[:3]]
        # CAPPED, and ranked by what would actually come up. A room of forty
        # produced forty entries of `regard: 1.0` on the first run of this
        # function — the payload-dump failure named two paragraphs up, made
        # while writing the warning about it. A presence brings up the person
        # they have a view about, not the roll of everyone standing there.
        def _salience(other):
            claim = minds[key][other]
            return (
                abs(1.0 - float(regard.get((key, other), 1.0))),   # a view
                0.0 if claim.get("believed_available") else 1.0,   # a surprise
                float(claim.get("strength") or 0.0),               # confidence
            )

        ranked = sorted(
            (o for o in present if o != key and o in (minds.get(key) or {})),
            key=lambda o: (_salience(o), o), reverse=True)[:4]
        known_here = {
            other: {
                "firsthand": (minds[key][other].get("heard_from") is None),
                "believes_present": bool(
                    minds[key][other].get("believed_available")),
                "regard": round(float(regard.get((key, other), 1.0)), 3),
            }
            for other in ranked
        }
        presences[key] = {
            "competence": dict(body.get("competence") or {}),
            "able": bool(body.get("available", True)),
            "condition": {n: round(float(v["level"]), 2)
                          for n, v in held_needs.items()},
            "strain": round(float(strains.get(key, 0.0)), 3),
            "standing_post": next(
                (p for p, who in watch.items() if who == key), None),
            "watches_stood": sum(
                (charter.get("stood") or {}).get(key, {}).values()),
            "can_bring_up": news,
            "knows_here": known_here,
            "strangers_here": sorted(present - set(known_here) - {key}),
            "blamed": int(blame.get(key, 0)),
            "knows_it_is_blamed": sorted(heard_blame.get(key, ())),
        }

    return {
        "place": place,
        "at_hours": float(charter.get("clock_hours") or 0.0),
        # What the place OBJECTIVELY is. For the Director to stage from, and
        # deliberately outside every presence's slice: a body knows the mill
        # is cold because it is standing in it, not because it read a level.
        "place_state": {
            key: {"level": round(float(u["level"]), 2),
                  "failing": out_of_band(u)}
            for key, u in (charter.get("upkeeps") or {}).items()
            if str(u.get("place") or "") == place},
        "posts_here": sorted(
            p for p, entry in posts.items()
            if str(entry.get("place") or "") == place),
        "recent_here": chronicle(
            [e for e in (events or []) if str(e.get("place") or "") == place],
            hours_per_day=hours_per_day)[-6:],
        "presences": presences,
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
