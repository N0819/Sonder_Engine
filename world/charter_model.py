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
    }


def normalize_body(key, entry):
    """A person the charter may assign.

    ``available`` is GROUND TRUTH -- whether this body can in fact stand a
    post. What the charter thinks about it lives in the roster, which is a
    belief and may be wrong. Keeping the two apart is the whole of §5.
    """
    entry = entry if isinstance(entry, dict) else {}
    return {
        "key": str(key),
        "competence": _tags(entry.get("competence")),
        "available": bool(entry.get("available", True)),
        "place": str(entry.get("place") or ""),
    }


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
    bodies = {
        str(k): normalize_body(k, v)
        for k, v in (stored.get("bodies") or {}).items()}

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
        "priority": priority,
        "roster": dict(stored.get("roster") or {}),
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
