"""The five primitives an institution is made of. Pure data, no I/O.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §3. Nothing here names a
genre: the engine knows that a number leaves a range and that a body can or
cannot service a tag. A lorebook decides whether the number is reactor coolant,
ward observations, or whether the office is sung at the hours.

THE FIVE, and the one naming trap:

  * **upkeep** -- a condition that must stay above a floor and drifts below it
    when unattended.
  * **post** -- a duty slot: a place, a competence requirement, the upkeeps it
    serves.
  * **competence** -- ``{tag: level}`` on a body. The tags are authored.
  * **watch** -- the assignment of bodies to posts for a window. Output, not
    input.
  * **charter** -- the institution: its upkeeps, its posts, the roster it
    BELIEVES it has, and its standing priority when it cannot fill everything.

A duty slot is a ``post``, never a ``station``: ``scene.stations`` already
means a body's within-room position, and a second spelling of a live word is
how this repo gets hurt.

Shapes are plain dicts with normalizers rather than dataclasses, matching
``living_world.normalize_living_world`` and ``attire.normalize_regions`` -- the
state has to survive a JSON round trip into ``world`` storage without a second
representation to keep in step.
"""

from __future__ import annotations

from .charter_figure import normalize_figures

#: A level is a fraction of nominal: 1.0 is perfectly kept, 0.0 is gone.
LEVEL_MAX = 1.0
LEVEL_MIN = 0.0

#: What an unnamed upkeep floor defaults to. Deliberately not zero: a floor of
#: zero means "this can never fail", which is never what an author means by
#: leaving the field blank, and a silently un-failable upkeep is exactly the
#: kind of authored blank that reads as complete and is not.
DEFAULT_FLOOR = 0.25


def _clamp(value, low=LEVEL_MIN, high=LEVEL_MAX):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, value))


def _tags(value):
    """``{tag: level}``, levels as non-negative ints, unnamed tags dropped."""
    out = {}
    if not isinstance(value, dict):
        return out
    for tag, level in value.items():
        tag = str(tag or "").strip()
        if not tag:
            continue
        try:
            level = int(level)
        except (TypeError, ValueError):
            level = 1
        out[tag] = max(0, level)
    return out


#: Public spelling of the tag normalizer, for the siblings. A private name
#: reached across modules is a facade waiting to be got wrong.
normalize_competence = _tags


def normalize_upkeep(key, entry):
    """One condition the institution owes.

    ``drift_per_hour`` is what neglect costs; ``service_per_hour`` is what one
    competent body restores. Both are per hour so a caller may advance any
    window without the model caring how long a turn is.
    """
    entry = entry if isinstance(entry, dict) else {}
    depends = entry.get("depends_on") or []
    if isinstance(depends, str):
        depends = [depends]
    return {
        "key": str(key),
        "place": str(entry.get("place") or ""),
        "level": _clamp(entry.get("level", LEVEL_MAX)),
        "floor": _clamp(entry.get("floor", DEFAULT_FLOOR)),
        "drift_per_hour": max(0.0, float(entry.get("drift_per_hour") or 0.0)),
        "service_per_hour": max(
            0.0, float(entry.get("service_per_hour") or 0.0)),
        "requires": _tags(entry.get("requires")),
        # WHAT THIS CONDITION IS MADE OUT OF. A tended post restores an
        # upkeep only as far as the things it draws on allow: a baker with a
        # full oven and no flour works at the rate the flour permits, however
        # competent and however present. Named upkeeps only, so a supply chain
        # is a graph over conditions the institution already owes rather than
        # a second kind of object.
        #
        # This is the field the town fixture demanded and the ship never
        # needed. It is also, deliberately, the only concession made to it:
        # `depends_on` plus the existing four fields is a supply chain, and no
        # goods, prices, inventories or markets were added to get one.
        "depends_on": [str(d) for d in depends if str(d or "").strip()],
    }


def normalize_post(key, entry):
    """One duty slot. ``serves`` names the upkeeps it tends."""
    entry = entry if isinstance(entry, dict) else {}
    serves = entry.get("serves") or []
    if isinstance(serves, str):
        serves = [serves]
    return {
        "key": str(key),
        "place": str(entry.get("place") or ""),
        "serves": [str(s) for s in serves if str(s or "").strip()],
        "requires": _tags(entry.get("requires")),
        # An optional authored reporting line names another POST, not a
        # person. Reassignment changes who briefs whom without rewriting
        # identity or history.
        "reports_to": str(entry.get("reports_to") or "").strip(),
    }


def normalize_body(key, entry):
    """A person the charter may assign.

    ``available`` is GROUND TRUTH -- whether this body can in fact stand a
    post. What the charter thinks about it lives in the roster, which is a
    belief and may be wrong. Keeping the two apart is the whole of §5.
    """
    entry = entry if isinstance(entry, dict) else {}
    body = {
        "key": str(key),
        # Durable institutional id (`key`) and scene-facing identity (`name`)
        # are separate so a promotion/rename does not rewrite past claims.
        "name": str(entry.get("name") or key),
        "competence": _tags(entry.get("competence")),
        "available": bool(entry.get("available", True)),
        # Set only when NEEDS put this body down, so needs may pick it up
        # again and nothing else is undone by them.
        "stood_down": bool(entry.get("stood_down", False)),
        "place": str(entry.get("place") or ""),
        # Where this body lives, as distinct from where it stands: the room
        # it walks back to when neither posted nor on an errand. Defaults to
        # the authored starting place, and survives every window after,
        # which is what lets `place` be honest about visits.
        "berth": str(entry.get("berth") or entry.get("place") or ""),
    }
    # An AUTHORED temperament only. The unauthored case is derived on demand
    # by `charter_temper.temperament_of` and stored nowhere, so the field is
    # absent for almost every body -- carrying five defaults per head would
    # be state that says nothing.
    if isinstance(entry.get("temperament"), dict):
        body["temperament"] = dict(entry["temperament"])
    # Presentation metadata never participates in planning.  The body key is
    # identity; these fields may change how that identity is addressed without
    # rewriting watches, memories or institutional history.
    for field in ("title", "rank", "given_name", "family_name",
                  "dialogue_color"):
        value = str(entry.get(field) or "").strip()
        if value:
            body[field] = value
    return body


def normalize_charter(stored):
    """A whole institution, from any shape, with its priority ordering closed.

    An upkeep absent from ``priority`` is appended in key order rather than
    dropped: a charter that silently stops caring about a condition because
    somebody forgot to rank it is the failure this repo keeps paying for in
    other subsystems.
    """
    stored = stored if isinstance(stored, dict) else {}
    upkeeps = {
        str(k): normalize_upkeep(k, v)
        for k, v in (stored.get("upkeeps") or {}).items()}
    posts = {
        str(k): normalize_post(k, v)
        for k, v in (stored.get("posts") or {}).items()}
    from .charter_identity import (
        materialize_body_names, normalize_naming_profile)
    naming = normalize_naming_profile(stored.get("naming"))
    raw_bodies = materialize_body_names(
        str(stored.get("key") or "charter"), stored.get("bodies") or {},
        naming)
    bodies = {
        str(k): normalize_body(k, v)
        for k, v in raw_bodies.items()}

    priority = [str(p) for p in (stored.get("priority") or [])
                if str(p) in upkeeps]
    for key in sorted(upkeeps):
        if key not in priority:
            priority.append(key)

    return {
        "key": str(stored.get("key") or "charter"),
        "upkeeps": upkeeps,
        "posts": posts,
        "bodies": bodies,
        "naming": naming,
        "priority": priority,
        "roster": dict(stored.get("roster") or {}),
        # Last planned watch is present institutional state: it tells a scene
        # which duty this body is actually standing.  Dropping it during
        # normalization erased role continuity at every persistence boundary.
        "watch": {
            str(post): str(body)
            for post, body in (stored.get("watch") or {}).items()
            if str(post) in posts and str(body) in bodies
        },
        "clock_hours": float(stored.get("clock_hours") or 0.0),
        # Standing conditions already written down, so a fact that persists
        # across windows is reported once rather than every window. Carried on
        # the charter rather than held in a runner, because a caller that
        # checkpoints and restores must restore this too or the restored run
        # re-reports everything it had already said.
        "reported": {
            str(kind): dict(entries)
            for kind, entries in (stored.get("reported") or {}).items()
            if isinstance(entries, dict)},
        # The room graph the bodies stand in, in `world.spatial`'s own shape,
        # or absent for an institution small enough to be one place. Carried
        # rather than passed so a charter is a single restorable object.
        "scene": stored.get("scene") or None,
        # One belief set per head, about the bodies that head has met. Held
        # beside the charter's own roster rather than replacing it: an
        # institution is an agent too, and its register is its belief, not a
        # summary of everyone else's.
        "minds": {
            str(holder): {str(s): dict(c) for s, c in claims.items()
                          if isinstance(c, dict)}
            for holder, claims in (stored.get("minds") or {}).items()
            if isinstance(claims, dict)},
        # Regard, standing and blame. Normalized by `charter_politics` at use
        # rather than here, to keep this module free of behaviour.
        "politics": dict(stored.get("politics") or {}),
        # People the institution can know without owning: the player, the
        # major characters, anyone with a mind of their own elsewhere. Not
        # bodies — never rostered, never planned, never blamed, and holding
        # no mind here. See `charter_figure`.
        "figures": normalize_figures(stored.get("figures")),
        # A promoted body remains an institutional projection: Charter may
        # try to roster it, but registered-character cognition and movement
        # own the person from this point forward.
        "bindings": {
            str(key): {
                "char_id": value.get("char_id"),
                "entity_id": str(value.get("entity_id") or ""),
                "name": str(value.get("name") or key),
                "promoted_turn": value.get("promoted_turn"),
            }
            for key, value in (stored.get("bindings") or {}).items()
            if str(key) in bodies and isinstance(value, dict)
            and value.get("char_id") is not None},
        # Per-body needs, and the ground each body has covered. Needs are the
        # reason `available` can stop being an authored flag; `travelled` is a
        # diagnostic carried beside the bodies rather than on them.
        "needs": {
            str(key): {str(n): dict(spec) for n, spec in held.items()
                       if isinstance(spec, dict)}
            for key, held in (stored.get("needs") or {}).items()
            if isinstance(held, dict)},
        # How much felt state is allowed to bias the watch bill. 0.0 is the
        # default and the shipped behaviour: mood is computed, reported, and
        # read by nothing. Above zero it joins standing and pressure on the
        # reluctance axis, which is the only way in it will ever get -- an
        # experiment with a dial, not a second planner.
        "mood_weight": float(stored.get("mood_weight") or 0.0),
        # Open social situations. Sparse: a population with nothing going on
        # between it carries none. See `charter_practice`.
        # Places where social detail is simulated at beat resolution. Empty
        # is the default and means none: a body off-screen keeps its needs,
        # feeling, belief and past, and simply is not gossiping this window.
        "news_keys": sorted(
            str(k) for k in (stored.get("news_keys") or ()) if k),
        "active_places": sorted(
            str(p) for p in (stored.get("active_places") or ()) if p),
        "practices": {
            str(k): dict(v) for k, v in (stored.get("practices") or {}).items()
            if isinstance(v, dict) and v.get("kind")},
        # Who has learned they are blamed. Blame was an institutional fact
        # that reached nobody; this is the record of it having been said out
        # loud to the person it landed on.
        "heard_blame": {
            str(k): sorted(str(x) for x in v)
            for k, v in (stored.get("heard_blame") or {}).items()},
        # Per-body felt state, in `mind/psychology_runtime`'s own persisted
        # shapes -- see `charter_feel`. Sparse: a body feeling nothing has no
        # entry, so a quiet institution carries an empty dict.
        "feel": {
            str(key): dict(entry)
            for key, entry in (stored.get("feel") or {}).items()
            if isinstance(entry, dict)},
        # What full strain multiplies the rest drift by
        # (`charter_needs.advance_needs`). None means the shipped default,
        # `charter_feel.STRAIN_REST_TOLL`; carried explicitly so an
        # experiment arm can pin it, including to zero.
        "strain_toll": (None if stored.get("strain_toll") is None
                        else max(0.0, float(stored.get("strain_toll")))),
        # Chance per HOUR that an off-duty body goes somewhere
        # (`charter_move.errands`). None means the shipped default,
        # `charter_move.ERRAND_RATE`; 0.0 pins the quiet control — nobody
        # stirs, which is the pre-circulation behaviour exactly.
        "errand_rate": (None if stored.get("errand_rate") is None
                        else max(0.0, float(stored.get("errand_rate")))),
        # Windows actually stood, per body per post. Bounded by bodies x
        # posts rather than by time, and the evidence a promotion call needs
        # to deliberate a project from -- a month at the same post is a
        # life's shape, and nothing else records it.
        "stood": {
            str(key): {str(p): int(n) for p, n in held.items()}
            for key, held in (stored.get("stood") or {}).items()
            if isinstance(held, dict)},
        "travelled": {str(k): int(v)
                      for k, v in (stored.get("travelled") or {}).items()},
    }


def meets(competence, requirement):
    """Does this competence map satisfy every tag of a requirement."""
    for tag, level in (requirement or {}).items():
        if int((competence or {}).get(tag, 0)) < int(level):
            return False
    return True


def out_of_band(upkeep):
    return float(upkeep["level"]) < float(upkeep["floor"])


def priority_rank(charter):
    """``{upkeep_key: rank}``, 0 being the thing the institution abandons last.

    The whole characterisation of an institution is this ordering -- life
    support above the galley, the office above the fire -- so it is a first
    class field and not a tie-break.
    """
    return {key: rank for rank, key in enumerate(charter["priority"])}
