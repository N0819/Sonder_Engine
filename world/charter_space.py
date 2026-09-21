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

from .spatial import (_ROUTE_MEMORY_BARRIERS, barrier_fastening,
                      neighbor_map, passable_path)

#: Rooms crossed beyond which a post is treated as unreachable within a
#: window. Not a hard wall in the fiction — somebody could walk further — but
#: an institution does not roster a body onto a post it cannot get to and back
#: from, and a charter that did would report posts filled that never were.
REACH_LIMIT = 8


def people_neighbors(scene):
    """The graph an institution's PEOPLE walk: the passable one, plus the
    doors a person can open.

    A PERSON HAS HANDS, and until this existed the engine did not say so. It
    already said it about a wolf -- `charter_creature.creature_neighbors` is
    "the passable one, plus shut doors when it can open them" -- while every
    human the charter moves planned on `passable_neighbors`, where a shut
    door is indistinguishable from a wall. So an institution could not roster
    a body onto a post one door from where it stood, and reported the post
    unfilled with `out_of_reach`.

    Measured (Aldermill, two-bubble run 2026-09-19, 60 beats): the inn's
    entire bill came back `{"tapster": "out_of_reach", "innkeeper":
    "out_of_reach", "cook": "out_of_reach"}` on every window. The staff stood
    in `inn_chambers`, one `closed_door` from the taproom; the reeve's seven
    officers sat behind the market square's shut door. Two characters walked
    that town for thirty beats each and `company` was empty on all sixty.

    WHICH EDGES, without a table of its own: `_ROUTE_MEMORY_BARRIERS` is
    already the engine's name for the passable set plus `closed_door`, and
    `normalize_barrier` has already ruled that sealed, bolted, welded and
    bricked are kinds of WALL. What it also folds away is the difference
    between a door that is shut and a door that is FASTENED, so the second
    filter asks the edge itself (`barrier_fastening`): a plain shut door
    opens, and a locked, padlocked, jammed, stuck or blocked one holds.

    That second filter is not a nicety. Without it this walks an institution
    through its own locked doors, and `TestABodyWalksTheRoute::
    test_a_shut_door_holds_the_body_where_it_stands` -- a tapster dispatched
    through an open door that then locks behind him -- said so immediately.

    The BEAT-scale graph is untouched. `passable_path` still refuses a shut
    door, because a walk must not advance through a door nobody has opened;
    this answers the different question of where a body can BE in four hours.
    """
    return neighbor_map(
        scene, _ROUTE_MEMORY_BARRIERS, directional=True,
        crossable=lambda edge: not barrier_fastening(edge.get("barrier")))


def travel_rooms(scene, from_room, to_room, limit=REACH_LIMIT, neighbors=None):
    """Rooms crossed walking from one place to another. ``None`` if unreachable.

    Zero for a body already there, which is the common case and the one worth
    being cheap: a watch bill mostly re-posts people where they already are.

    ``neighbors`` is the caller's own graph, exactly as `walk_route` takes it
    and for the same reason: the two must never disagree about whether a post
    is reachable, so a distance exists exactly when a route does. Absent, this
    is the ordinary passable walk it has always been.
    """
    a, b = str(from_room or ""), str(to_room or "")
    if not a or not b:
        return None
    if a == b:
        return 0
    if neighbors is not None:
        route = _route_on(neighbors, a, b, limit)
        return len(route) - 1 if route else None
    path = passable_path(scene, a, b, limit=limit)
    return len(path) if path else None


def walk_route(scene, from_room, to_room, limit=REACH_LIMIT, cache=None,
               neighbors=None):
    """The rooms a body walks from one place to another, INCLUSIVE of both
    ends -- the courier's `route` shape -- or ``None`` if unreachable.

    Same pathfinder as `travel_rooms`, kept beside it so the two can never
    disagree about whether a post is reachable: a route exists exactly when
    a distance does. ``cache`` maps ``(origin, target) -> route-or-None`` and
    may outlive the call for a fixed scene, as `reach_map`'s does.

    `neighbors` IS THE GRAPH THE BODY ACTUALLY WALKS, when the caller has
    one, and it is the difference between a decision and a route agreeing.
    `passable_path`'s graph is the ordinary one -- open ways, open doors and
    membranes -- and a body whose own graph is WIDER than that decides to go
    somewhere the planner will not plan to, so the move is dropped and
    nothing says why.

    Measured (chat 117, turns 18-24): a carbonic stalker with
    `can_open_doors` smelled its prey through a shut containment door,
    `hunt_moves` returned a walk into the corridor beyond it -- deciding on
    `creature_neighbors`, which honours that flag -- and `_dispatch` asked
    `passable_path`, which does not, got None, and left the body standing
    for seven straight beats. The re-check inside `_advance` was already
    against `neighbors`; only the PLAN was against a different graph.
    """
    a, b = str(from_room or ""), str(to_room or "")
    if not a or not b:
        return None
    if a == b:
        return [a]
    cache = {} if cache is None else cache
    pair = (a, b)
    if pair not in cache:
        if neighbors is not None:
            cache[pair] = _route_on(neighbors, a, b, limit)
        else:
            path = passable_path(scene, a, b, limit=limit)
            cache[pair] = [a] + [str(r) for r in path] if path else None
    return list(cache[pair]) if cache[pair] else None



def room_traffic(scene, registry, limit=REACH_LIMIT, neighbors=None):
    """``{room: weight}`` -- how much of a town's walking crosses each room.

    A TOWN IS BUSY WHERE ITS ROUTES MEET, AND THAT IS A PROPERTY OF THE MAP.
    Presence in this engine is a body's `place`, so a room holds people only
    when somebody is POSTED there -- and nobody is posted to a market square.
    Measured (two_lives v11, 2026-09-20): the square of a forty-body town held
    one watchman while the forge held five and the mill loft five, so a
    traveller who stood in the town's own hub had exactly one person to talk
    to and got thirteen answers out of him.

    Errands fix that when they run, but they are the simulation's business and
    they need hours. This is the half that needs no clock at all: which rooms
    people CROSS to get between the places they are posted at is fixed by the
    topology and the watch bill, so it can be derived once and rendered at any
    speed. A square between a mill, a smithy, an inn and a hall is busy by
    construction; a lockup at the end of a passage is not.

    Weighted by the bodies at each end, because traffic between two crowded
    institutions is heavier than between two quiet ones, and counted only for
    rooms a route passes THROUGH -- an endpoint's own population is already
    presented as itself and must not be counted twice.

    TEXTURE, NEVER PEOPLE. This says a room is walked through; it names
    nobody, and no caller may turn a weight into a body. The bodies a room
    holds are the ones standing in it, and a derived second population that
    could contradict the first is exactly what `charter_crowd` refuses.
    """
    scene = scene if isinstance(scene, dict) else {}
    rooms = scene.get("rooms") or {}
    if not rooms:
        return {}
    graph = neighbors if neighbors is not None else people_neighbors(scene)

    # WHERE THE TOWN'S PEOPLE STAND, and how many at each -- the endpoints
    # every route runs between.
    weight = {}
    for item in ((registry or {}).get("items") or {}).values():
        state = item.get("state") if isinstance(item, dict) else None
        for body in ((state or {}).get("bodies") or {}).values():
            place = str((body or {}).get("place") or "")
            if place in rooms:
                weight[place] = weight.get(place, 0) + 1
    if len(weight) < 2:
        return {}

    traffic, cache = {}, {}
    places = sorted(weight)
    for i, origin in enumerate(places):
        for target in places[i + 1:]:
            key = (origin, target)
            if key not in cache:
                cache[key] = walk_route(scene, origin, target, limit=limit,
                                        neighbors=graph)
            route = cache[key]
            if not route or len(route) < 3:
                continue
            # Both directions of one pair of endpoints, which is what a day of
            # errands between them actually is.
            pair = (weight[origin] + weight[target])
            for room in route[1:-1]:
                traffic[str(room)] = traffic.get(str(room), 0) + pair
    return traffic

def _route_on(neighbors, a, b, limit):
    """Breadth-first route over a caller's own graph, inclusive of both ends,
    or None. Deterministic: neighbours are taken in sorted order, so one
    scene always yields one route."""
    from collections import deque

    if a not in neighbors:
        return None
    seen = {a: None}
    queue = deque([(a, 0)])
    while queue:
        here, depth = queue.popleft()
        if here == b:
            route = []
            while here is not None:
                route.append(here)
                here = seen[here]
            return list(reversed(route))
        if depth >= limit:
            continue
        for nxt in sorted(neighbors.get(here) or ()):
            if nxt not in seen:
                seen[nxt] = here
                queue.append((nxt, depth + 1))
    return None


def refresh_reach(reach, scene, places, bodies, moved, limit=REACH_LIMIT,
                  cache=None, neighbors=None):
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
                         limit=limit, cache=cache, neighbors=neighbors))
    return out


def reach_map(scene, places, bodies, limit=REACH_LIMIT, cache=None,
              neighbors=None):
    """``{(body, place): rooms}`` for every body/place pair that is reachable.

    Computed once per window and handed to the planner, because the same body
    is weighed against several posts and re-walking the graph for each pairing
    is how an O(bodies x posts) planner becomes an O(bodies x posts x rooms)
    one. Unreachable pairs are ABSENT rather than stored as infinity, so a
    caller that forgets to check gets a KeyError instead of a body silently
    posted across the ship.

    ``cache`` maps ``(origin_room, place) -> rooms-or-None`` and MAY OUTLIVE
    the call: for a fixed scene the walk between two rooms never changes, so
    a caller advancing many windows hands the same dict back in and pays for
    each origin once per run rather than once per window. That is what makes
    a population that actually circulates (`charter_move.errands`) cost
    lookups rather than graph walks. It is keyed by rooms alone, so a cache
    must not be shared between two callers walking DIFFERENT graphs -- one
    `people_neighbors` run and one passable run would read each other's
    answers.

    ``neighbors`` is the graph to walk, `walk_route`'s own argument threaded
    through: `people_neighbors` for an institution's people, absent for the
    ordinary passable walk this has always made.
    """
    out = {}
    cache = {} if cache is None else cache
    for key, body in (bodies or {}).items():
        origin = str(body.get("place") or "")
        for place in places:
            pair = (origin, str(place))
            if pair not in cache:
                cache[pair] = travel_rooms(scene, origin, place, limit=limit,
                                           neighbors=neighbors)
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


def commons_places(charter):
    """Every place its people may go FOR ITS OWN SAKE, tended by nobody.

    A post is a place a body is SENT to and an upkeep is a place work is DONE
    at, so `charter_places` -- their union -- is the whole of where the
    institution's WORK is, and nothing more. A room whose purpose is BEING IN
    it is neither, so for as long as circulation routed off-duty bodies only
    to charter places, a lounge, a chapel, a park, a market square was
    somewhere the simulated population could never go however social it was.
    Measured on chat 98: 7 work places against 45 rooms, and the run's author
    had to invent an upkeep nobody serves just to make one room reachable --
    which is a condition the institution now owes forever and will report as
    failing, to say that people sit there.

    Two sources, and the first needed no new field: a MARKET already carries a
    place and is by definition somewhere a body goes to get something for
    itself. The second is `commons`, authored, for the room that answers to
    nothing at all.

    A BERTH IS DELIBERATELY NOT HERE. It is somebody's own place rather than a
    place people go, `charter_move.homecomings` already routes a body to its
    own without needing reach, and the set of distinct berths grows with the
    population -- so folding them in would multiply `reach_map`'s bodies x
    places walk by the population itself on any world that berths people
    individually.
    """
    places = {str(p) for p in (charter.get("commons") or ()) if str(p)}
    markets = (charter.get("economy") or {}).get("markets") or {}
    places.update(str(m.get("place") or "") for m in markets.values()
                  if isinstance(m, dict))
    places.discard("")
    return sorted(places)


def frequented_places(charter):
    """Every place circulation may route a body to: the work and the commons.

    The set `reach_map` is walked over and `charter_move.errands` filters
    against. Keeping it distinct from `charter_places` is the point -- the
    planner still fills posts, and only a post's own place can be one.
    """
    return sorted(set(charter_places(charter)) | set(commons_places(charter)))
