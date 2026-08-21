"""Where the bodies are, and what it costs them to get to a post.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §3. Until now a ``place`` was
a free string and a body could stand any post instantly, which is a fair
simplification for six people in one hull and a bad one for five hundred
across ninety compartments: the nearest rated hand is a real constraint, and
a watch bill that ignores distance is a watch bill nobody could stand.

ONE PATHFINDER, NOT A SECOND. Distance comes from ``world.spatial``'s
``passable_path`` over the same scene graph everything else walks — the same
rule ``passable_neighbors`` was lifted out for when crowds needed it. This
module imports the FACADE, never a ``spatial_*`` sibling.

Travel is a cost on assignment, not a simulation of walking. Whether a body
physically moves is the scene's business; what a charter needs to know is that
posting the cook four compartments away from the only fire is worse than
posting the hand already standing beside it.
"""

from __future__ import annotations

from .spatial import passable_path

#: Rooms crossed beyond which a post is treated as unreachable within a
#: window. Not a hard wall in the fiction — somebody could walk further — but
#: an institution does not roster a body onto a post it cannot get to and back
#: from, and a charter that did would report posts filled that never were.
REACH_LIMIT = 8


def travel_rooms(scene, from_room, to_room, limit=REACH_LIMIT):
    """Rooms crossed walking from one place to another. ``None`` if unreachable.

    Zero for a body already there, which is the common case and the one worth
    being cheap: a watch bill mostly re-posts people where they already are.
    """
    a, b = str(from_room or ""), str(to_room or "")
    if not a or not b:
        return None
    if a == b:
        return 0
    path = passable_path(scene, a, b, limit=limit)
    return len(path) if path else None


def refresh_reach(reach, scene, places, bodies, moved, limit=REACH_LIMIT):
    """Update reach for the bodies that MOVED, and no others.

    `reach_map` walks every body against every place. Once bodies actually
    relocate to their posts, `run`'s "did anybody move" guard fires most
    windows, and a full rebuild for the sake of a handful of movers measured
    as 3.5 of 9.6 seconds -- the largest single cost in the profile, and one
    created by adding movement rather than by anything movement needed.
    """
    if not moved:
        return reach
    out = {k: v for k, v in (reach or {}).items() if k[0] not in moved}
    out.update(reach_map(scene, places,
                         {k: bodies[k] for k in moved if k in bodies},
                         limit=limit))
    return out


def reach_map(scene, places, bodies, limit=REACH_LIMIT):
    """``{(body, place): rooms}`` for every body/place pair that is reachable.

    Computed once per window and handed to the planner, because the same body
    is weighed against several posts and re-walking the graph for each pairing
    is how an O(bodies x posts) planner becomes an O(bodies x posts x rooms)
    one. Unreachable pairs are ABSENT rather than stored as infinity, so a
    caller that forgets to check gets a KeyError instead of a body silently
    posted across the ship.
    """
    out = {}
    cache = {}
    for key, body in (bodies or {}).items():
        origin = str(body.get("place") or "")
        for place in places:
            pair = (origin, str(place))
            if pair not in cache:
                cache[pair] = travel_rooms(scene, origin, place, limit=limit)
            rooms = cache[pair]
            if rooms is not None:
                out[(key, str(place))] = rooms
    return out


def charter_places(charter):
    """Every place this institution has a post or an upkeep at."""
    places = {str(p["place"]) for p in charter["posts"].values() if p["place"]}
    places.update(str(u["place"]) for u in charter["upkeeps"].values()
                  if u["place"])
    return sorted(places)
