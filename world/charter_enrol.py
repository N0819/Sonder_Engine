"""Enrolment: the deterministic FILL behind a person the Director rendered
with no plan behind them.

THE CLASS. A person the story names is a member of a real institution from
the beat they are seen, never of a placeholder. The old answer to "who
simulates a person the generator did not mint" was an ambient charter --
an institution of none, no posts, no upkeeps, berth = the room they were
first seen in -- and every reader of the registry then had to special-case
it (no home, no dwelling, no seat, no reporting line), while the person it
held shadowed the real post-holder standing beside them (Harrowmere replay
2026-09-03: seven mints, six shadows). Under plan-and-render
(docs/design/DESIGN_WRITERS_ROOM_PLAN.md § 2) a mint with no plan files a
planning need with the committed surface attached, and THIS module answers
a person-need in the same commit by enrolling the person somewhere real:

1. the institution whose post the role names, when a seat is open under
   the head-seat rule (`charter_generate._post_seats`, `HEAD_SEATS`) or the
   crew ceiling (`CREW_SIZE`); the post's reporting chain comes with it;
2. else, standing in a LODGING (a room that is both a workplace and a berth
   of one charter -- an inn's taproom with the staff sleeping over it), a
   GUEST of that charter, berthed there, with a departure the town runs;
3. else the HOUSEHOLDS charter -- the institution whose work is keeping its
   own berths -- in a house under `BERTH_CEILING`, nearest the room they
   were seen in; when every house is full, the least-full one and a
   room-need for a dwelling, filed for the Writers' Room;
4. else, in a story with no town at all, a minimal households charter
   minted for the story, and the same room-need.

The enrolled body is dealt a surface by the look law and RECONCILED with
what was seen: an axis the Director's description names another pool value
of takes the seen value, because nothing about what a person looked like
was ever the plan's to contradict. No model call anywhere.
"""
from __future__ import annotations

import hashlib
import re

from world.charter_generate import BERTH_CEILING, CREW_SIZE, _post_seats
from world.charter_model import normalize_body
from world.charter_needs import seed_needs
from world.charter_roster import seed_roster
from world.charter_surface import (AXES, RENDER_CHARS, _phrase_in,
                                   deal_surface, looks_profile)

#: The key a story's households charter is minted under when it has none.
HOUSEHOLDS_CHARTER = "households"
#: How long a guest keeps a berth at a lodging before the town runs their
#: departure (`depart_guests`): three days, the same horizon the harm
#: model gives a hurt body to recover.
GUEST_STAY_HOURS = 72.0
#: How the fill enrolled a person; closed, for the record and the tests.
ENROL_HOW = ("post", "guest", "household", "minted_households")


def enrolled_body_key(name):
    """A stable key for a person the story named and no generator minted."""
    slug = re.sub(r"[^a-z0-9]+", "_",
                  " ".join(str(name or "").split()).casefold()).strip("_")
    digest = hashlib.sha256(str(name or "").encode("utf-8")).hexdigest()[:6]
    return "%s:%s" % (slug[:32] or "person", digest)


def _text(value, limit=200):
    return " ".join(str(value or "").split())[:limit]


def _role_words(name, role=""):
    """The words a role can be read from: the role the need names, else
    the name's own words bare of determiners and titles ("The Blacksmith"
    -> blacksmith). Stems through `charter_observe._stem_role_word` so a
    noun meets the duty it names."""
    from persist.commit import strip_name_titles
    from world.charter_observe import _determiners, _stem_role_word
    text = _text(role) or strip_name_titles(_text(name))
    skip = set(_determiners())
    ordered = [w for w in re.findall(r"[a-z0-9]+", text.casefold())
               if w not in skip and len(w) > 1]
    # ORDERED, head last, so `posts_for_role` can read the head noun.
    return [_stem_role_word(w) for w in ordered]


def posts_for_role(registry, words):
    """``[(charter_key, post_key)]`` at the strongest grade a role noun
    reaches across every charter (`charter_observe._post_forms`: a post's
    key, title, public noun, upkeeps served and authority entries, as
    stems). Exact forms first, then forms containing the words; two at the
    strongest grade is still a list -- the caller decides whether two is
    nobody."""
    if not words:
        return []
    from world.charter_observe import _post_forms
    exact, within, by_head = [], [], []
    head = {words[-1]} if isinstance(words, list) else None
    words = set(words)
    for charter_key, item in sorted((registry.get("items") or {}).items()):
        state = (item or {}).get("state") or {}
        forms = _post_forms(state)
        for post_key, stems in sorted(forms.items()):
            if any(words == form for form in stems):
                exact.append((str(charter_key), str(post_key)))
            elif any(words <= form for form in stems):
                within.append((str(charter_key), str(post_key)))
            elif head and any(head == form for form in stems):
                # The label's HEAD noun alone names the post: English puts
                # the kind of person last and the qualifier first, so "the
                # bridge watchman" is a watchman with a station in front
                # (`director_floors._role_noun_matches`, the same rule).
                by_head.append((str(charter_key), str(post_key)))
    return exact or within or by_head


def seat_open(state, post_key):
    """Is there room on this post: under its fixed seats when it has them
    (a head post holds `HEAD_SEATS`), else under the crew ceiling."""
    posts = state.get("posts") or {}
    if post_key not in posts:
        return False
    seats = _post_seats(posts)
    ceiling = seats.get(post_key, CREW_SIZE)
    holders = sum(
        1 for body in (state.get("bodies") or {}).values()
        if isinstance(body, dict) and body.get("available", True)
        and str(body.get("home_post") or "") == post_key)
    return holders < ceiling


def work_and_berths(state):
    """``(work places, {berth: sleeper count})`` for one charter."""
    from world.charter_runtime import charter_work_places
    berths = {}
    for body in (state.get("bodies") or {}).values():
        if not isinstance(body, dict) or body.get("departed"):
            continue
        berth = str(body.get("berth") or "")
        if berth:
            berths[berth] = berths.get(berth, 0) + 1
    return charter_work_places(state), berths


def lodging_charter_for(registry, place):
    """The charter for which `place` is both a workplace and a berth -- a
    house that lodges people is one whose staff sleep where they serve.
    The households charter is the one institution excluded: its work IS
    keeping its berths (`households_charter_key`), so every house it keeps
    is a workplace-and-berth without lodging anybody. None when no charter
    reads the room that way."""
    place = str(place or "")
    if not place:
        return None
    households = households_charter_key(registry)
    for charter_key, item in sorted((registry.get("items") or {}).items()):
        if str(charter_key) == households:
            continue
        state = (item or {}).get("state") or {}
        work, berths = work_and_berths(state)
        if place in work and place in berths:
            return str(charter_key)
    return None


#: A households charter keeps at least this many houses: one house whose
#: staff sleep where they serve is a lodging, not a town's households.
HOUSEHOLDS_MIN_HOUSES = 2


def households_charter_key(registry):
    """The institution whose work is keeping its own berths: every upkeep
    it serves is placed where one of its members sleeps, across at least
    `HOUSEHOLDS_MIN_HOUSES` such houses (an inn whose staff sleep over the
    one taproom keeps one, and lodges people; a households charter keeps
    the town's houses). Two such: the one with more houses. Else the
    charter minted under `HOUSEHOLDS_CHARTER` for a story with no town, if
    one exists; else None."""
    best, best_rank = None, None
    items = registry.get("items") or {}
    for charter_key, item in sorted(items.items()):
        state = (item or {}).get("state") or {}
        upkeep_places = {
            str(u.get("place") or "")
            for u in (state.get("upkeeps") or {}).values()
            if isinstance(u, dict) and str(u.get("place") or "")}
        _work, berths = work_and_berths(state)
        if not upkeep_places or not berths:
            continue
        if not upkeep_places <= set(berths):
            continue
        houses = len(upkeep_places & set(berths))
        if houses < HOUSEHOLDS_MIN_HOUSES:
            continue
        rank = (houses, len(berths), -len(str(charter_key)))
        if best_rank is None or rank > best_rank:
            best, best_rank = str(charter_key), rank
    if best is None and HOUSEHOLDS_CHARTER in items:
        return HOUSEHOLDS_CHARTER
    return best


def _room_distances(scene, start):
    """BFS hops over the passable graph from `start`; {} without a scene."""
    if not isinstance(scene, dict) or not start:
        return {}
    try:
        from world.spatial import passable_neighbors
        neighbors = passable_neighbors(scene)
    except Exception:
        return {}
    dist = {str(start): 0}
    frontier = [str(start)]
    while frontier:
        nxt = []
        for room in frontier:
            for other in neighbors.get(room, ()) or ():
                other = str(other)
                if other not in dist:
                    dist[other] = dist[room] + 1
                    nxt.append(other)
        frontier = nxt
    return dist


def berth_in_households(state, place, scene=None, ceiling=BERTH_CEILING):
    """``(berth, full)``: the house under the ceiling nearest the room the
    person was seen in (fewest hops, then fewest sleepers, then name); when
    every house is full, the least-full one and ``full=True`` so the caller
    files a room-need."""
    _work, berths = work_and_berths(state)
    if not berths:
        return "", True
    dist = _room_distances(scene, place)
    far = max(dist.values(), default=0) + 1
    ranked = sorted(berths.items(),
                    key=lambda kv: (dist.get(kv[0], far), kv[1], kv[0]))
    for berth, count in ranked:
        if count < ceiling:
            return berth, False
    least = min(berths.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return least, True


def reconcile_surface(charter_key, body_key, looks, post, seen):
    """Deal a surface and let what was SEEN win on every axis the
    description names another pool value of. ``seen`` is the Director's
    committed description; it settles as the surface's render."""
    surface = deal_surface(charter_key, body_key, looks, post=post)
    seen = _text(seen, RENDER_CHARS)
    if not seen:
        return surface
    for axis in AXES:
        dealt = str(surface.get(axis) or "")
        for value in looks.get(axis) or ():
            if not value or value == dealt:
                continue
            if _phrase_in(value, seen) and not (dealt and _phrase_in(dealt, value)):
                surface[axis] = value
                break
    surface["rendered"] = seen
    return surface


def _add_body(state, charter_key, body_key, *, name, place, berth, post_key,
              seen, extra=None):
    posts = state.get("posts") or {}
    post = posts.get(post_key) if post_key else None
    competence = {}
    if isinstance(post, dict):
        competence = {str(tag): 1 for tag in (post.get("requires") or {})}
    raw = {"key": body_key, "name": name, "place": place, "berth": berth,
           "home_post": post_key or "", "competence": competence,
           "available": True}
    raw.update(extra or {})
    body = normalize_body(body_key, raw)
    for field, value in (extra or {}).items():
        body[field] = value
    looks, _source = looks_profile(state)
    body["surface"] = reconcile_surface(charter_key, body_key, looks, post, seen)
    state.setdefault("bodies", {})[body_key] = body
    state.setdefault("needs", {})[body_key] = seed_needs({body_key: body})[body_key]
    state.setdefault("roster", {})[body_key] = seed_roster({body_key: body})[body_key]
    return body


def _post_berth(state, post_key, place):
    """Where the post's present holders sleep (the most common berth), else
    the post's own place, else where the person was seen."""
    counts = {}
    for body in (state.get("bodies") or {}).values():
        if isinstance(body, dict) and str(body.get("home_post") or "") == post_key:
            berth = str(body.get("berth") or "")
            if berth:
                counts[berth] = counts.get(berth, 0) + 1
    if counts:
        return max(sorted(counts), key=lambda b: counts[b])
    post = (state.get("posts") or {}).get(post_key) or {}
    return str(post.get("place") or "") or str(place or "")


def enrol_person(cid, need, frame_id=None, scene=None):
    """Answer one person-need by enrolment. Returns the record
    ``{ref, how, charter, body, post, berth, room_need, notes}`` or None
    when the need names nobody.

    A person the registry already holds under that name (any charter) is
    returned as they are: the fill is a floor, not a claimant.
    """
    from world.charter_runtime import (registry_for, registry_for_update,
                                       save_registry)

    surface = (need or {}).get("surface") if isinstance(need, dict) else {}
    surface = surface if isinstance(surface, dict) else {}
    name = _text(surface.get("name"), 120)
    if not name:
        return None
    place = _text(surface.get("room"), 120)
    seen = str(surface.get("description") or "")
    role = _text(surface.get("role"), 120)

    shared = registry_for(cid, frame_id)
    for charter_key, item in (shared.get("items") or {}).items():
        for body_key, body in ((item.get("state") or {}).get("bodies")
                               or {}).items():
            if not isinstance(body, dict) or body.get("departed"):
                continue
            for alias in (str(body.get("name") or ""), str(body_key)):
                if alias and alias.casefold() == name.casefold():
                    return {"ref": {"charter": str(charter_key),
                                    "body": str(body_key)},
                            "how": "held", "charter": str(charter_key),
                            "body": str(body_key), "post": "",
                            "berth": str(body.get("berth") or ""),
                            "room_need": False, "notes": []}

    registry = registry_for_update(cid, frame_id)
    items = registry.setdefault("items", {})
    body_key = enrolled_body_key(name)
    notes = []
    record = {"ref": None, "how": "", "charter": "", "body": body_key,
              "post": "", "berth": "", "room_need": False, "notes": notes}

    # 1. The institution whose post the role names, when a seat is open.
    words = _role_words(name, role)
    candidates = [(c, p) for c, p in posts_for_role(registry, words)
                  if c in items and seat_open(items[c].get("state") or {}, p)]
    if candidates:
        if len({c for c, _p in candidates}) > 1:
            notes.append("role names posts in more than one institution; "
                         "enrolled in the first by key")
        charter_key, post_key = candidates[0]
        state = items[charter_key]["state"]
        berth = _post_berth(state, post_key, place)
        _add_body(state, charter_key, body_key, name=name, place=place,
                  berth=berth, post_key=post_key, seen=seen)
        record.update(how="post", charter=charter_key, post=post_key,
                      berth=berth)
    else:
        if words and posts_for_role(registry, words):
            notes.append("every seat of the post the role names is held; "
                         "enrolled without it")
        # 2. A guest of the house that lodges people where the person stood.
        lodging = lodging_charter_for(registry, place)
        if lodging:
            state = items[lodging]["state"]
            until = float(state.get("clock_hours") or 0.0) + GUEST_STAY_HOURS
            _add_body(state, lodging, body_key, name=name, place=place,
                      berth=place, post_key="", seen=seen,
                      extra={"guest": True, "guest_until": until})
            record.update(how="guest", charter=lodging, berth=place)
        else:
            # 3. The households charter, in a house with room.
            households = households_charter_key(registry)
            if households:
                state = items[households]["state"]
                berth, full = berth_in_households(state, place, scene)
                _add_body(state, households, body_key, name=name,
                          place=place, berth=berth or place, post_key="",
                          seen=seen)
                record.update(how="household", charter=households,
                              berth=berth or place, room_need=full)
                if full:
                    notes.append("every house is at the berth ceiling; a "
                                 "dwelling is owed")
            else:
                # 4. No town: a minimal households charter for the story.
                item = items.setdefault(HOUSEHOLDS_CHARTER, {"state": {
                    "key": HOUSEHOLDS_CHARTER, "posts": {}, "upkeeps": {},
                    "priority": [], "bodies": {}}})
                state = item.setdefault("state", {})
                state.setdefault("key", HOUSEHOLDS_CHARTER)
                _add_body(state, HOUSEHOLDS_CHARTER, body_key, name=name,
                          place=place, berth=place, post_key="", seen=seen)
                record.update(how="minted_households",
                              charter=HOUSEHOLDS_CHARTER, berth=place,
                              room_need=True)
                notes.append("no institution keeps its own berths here; a "
                             "households charter was minted and a dwelling "
                             "is owed")
    record["ref"] = {"charter": record["charter"], "body": body_key}
    save_registry(cid, registry, frame_id)
    return record


def depart_guests(charter, at_hours):
    """A guest whose stay has run out leaves: unavailable, standing
    nowhere, marked departed so no reader lists them. Returns
    ``(charter, [body keys departed])``; pure on the charter dict."""
    departed = []
    for body_key, body in (charter.get("bodies") or {}).items():
        if not isinstance(body, dict) or not body.get("guest"):
            continue
        if body.get("departed"):
            continue
        until = body.get("guest_until")
        if until is None or float(at_hours) < float(until):
            continue
        body["departed"] = True
        body["available"] = False
        body["place"] = ""
        departed.append(str(body_key))
    return charter, departed
