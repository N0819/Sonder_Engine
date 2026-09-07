"""Bodies going to the posts they were given, and the ground that costs.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §3. Until now a body had a
``place`` and stayed in it forever: reach constrained who COULD be posted and
nobody ever actually went. That is a watch bill nobody stands, and it also
quietly froze everything downstream — the same faces met in the same rooms
every window, so gossip could only ever circulate within a berth.

A BODY WALKS THE ROUTE NOW, ONE ROOM AT A TIME. The first version of this
module said the opposite, on purpose: "a body assigned a post is AT that post
for the window; the rooms between are counted as distance travelled and are
not otherwise simulated ... inventing a per-room walk here would be a second
movement system competing with the one `world.spatial` already owns." Half of
that argument still stands and is kept: there is still ONE pathfinder
(`charter_space.walk_route` over `world.spatial.passable_path`, the graph
every other body walks), no re-planning around a shut door, and no clock of
its own. What changed is the OBJECT a body carries between windows. It was a
scalar `place`; it is now the courier's shape (`story/couriers.py`): a route
computed once at dispatch, a leg index, and `place` always equal to the room
at that leg -- "a position, not an ETA". Three things the scalar could not
give and the prototype needed, measured on the `small_town` fixture before
this change (a smith six rooms from his forge stood at it in the same window
he left home, and `travelled` said 6 without saying which six):

  * **The rooms between are walked**, so a body is in every room it passed
    and a promoted body can inherit the edges it earned (`walked`), rather
    than a count of rooms nobody can name.
  * **A shut door holds a body somewhere specific**, this window and every
    window until it opens, instead of being paid for as distance and passed
    through.
  * **A long walk is long.** A window buys `WALK_ROOMS_PER_HOUR` rooms per
    hour and no more; a body still en route at the window's end stands in the
    street, is counted in that street's crowd, and finishes next window.

WHAT IT UNLOCKS, which is more than it costs:

  * **Distance is a real quantity per body**, so "who moves the most" has an
    answer and the answer means something.
  * **Co-presence changes**, so who talks to whom changes, so belief spreads
    along the paths people actually walk rather than pooling in berths.
  * **Reach is recomputed when it matters** — `charter_run` already guards for
    a body's place changing, and until now that guard never fired once.

A BODY IN TRANSIT COUNTS WHERE IT STANDS. `charter_crowd.members_of` reads
`place`, and `place` is the current leg's room, so a body caught mid-walk at
the window's end is in that street's crowd and nowhere else. There is no
in-transit limbo, deliberately: a courier held at a gate is "somewhere
specific, which is exactly what makes him catchable", and a townsperson on
the way to market is the same.
"""

from __future__ import annotations

import zlib

from .charter_space import walk_route

#: Chance per HOUR that an off-duty body goes somewhere — per hour, not per
#: window, because every other rate in this package is per hour and a rate
#: whose unit quietly depends on the caller's window size is an authored
#: number that fails silently (the first version was per-window, and the
#: same charter circulated four times harder at one-hour windows than at
#: four). ~0.24 per four-hour window: one or two outings a day. A charter
#: pins its own value (including 0.0, the quiet control) via
#: ``errand_rate``; None means this.
ERRAND_RATE = 0.06

#: Rooms a walking body crosses per simulated hour. THE COURIER'S OWN PACE,
#: restated: `story/couriers.py` pays one passable edge per
#: ``PACES["walking"]`` (600) seconds on foot, and a townsperson on an errand
#: walks the same streets at the same speed. Pinned equal by
#: `tests/test_charter_traversal.py` rather than imported, because `world/`
#: does not import `story/`. At the default four-hour window this buys 24
#: rooms, so on a settlement-sized map nearly every walk finishes inside the
#: window it began -- the bound only bites on a long road or a short window,
#: which is when it should.
WALK_ROOMS_PER_HOUR = 6.0

#: WHAT AN EDGE IS DECIDES WHAT IT COSTS, and the constant above assumes it
#: is a street.
#:
#: 6 rooms an hour is 600 seconds -- TEN MINUTES -- to cross one edge, which
#: is right for the courier it was pinned to: a town's edge is a road between
#: two places and a body walks it for ten minutes. A SCENE's edge is a
#: doorway, and a body crosses one in the time it takes to walk the room it
#: is standing in. Measured on the descent story (chat 117): a 24-pace
#: service spine is about eighteen seconds at a walking pace, and the beats
#: of that story declare 6 to 45 seconds each -- so at the town rate a
#: creature that decided to hunt bought about a thirtieth of a doorway per
#: beat and would have arrived in roughly thirty turns, having decided in
#: one. The story it was in is four minutes long.
#:
#: So the cost of a leg is derived from the ROOM being crossed rather than
#: assumed: its own measured span at a walking pace, and the edge's own
#: `distance` word where the plan gave it one. Nothing about a town changes
#: -- a settlement's rooms are its streets and its spans are street-sized --
#: and a corridor stops costing what a road costs.
#:
#: Paces a walking body covers in a second. A pace is about the metre this
#: engine's extents are drawn in, and 1.3 m/s is an ordinary walk.
WALK_PACES_PER_SECOND = 1.3

#: What the edge's own `distance` word is worth in paces, where the room's
#: measurement does not already say. `adjacent` is a doorway you step
#: through; the two long words are the ones the plan schema says "take more
#: than one beat to cross", and they keep costing what a road costs.
WALK_EDGE_PACES = {"adjacent": 2.0, "near": 8.0, "far": 240.0,
                   "remote": 780.0}


def edge_seconds(scene, here, nxt) -> float:
    """How long a body takes to cross from `here` into `nxt`, in seconds.

    The room's own span plus what the edge itself costs. A scene that has
    measured nothing falls back to the town rate, so an unmeasured world is
    exactly what it was.
    """
    from world.spatial import room_span

    town = 3600.0 / WALK_ROOMS_PER_HOUR
    rooms = (scene or {}).get("rooms") if isinstance(scene, dict) else None
    if not isinstance(rooms, dict) or str(here) not in rooms:
        return town
    room = rooms.get(str(here)) or {}
    edge_paces = None
    for edge in room.get("adjacent") or ():
        if isinstance(edge, dict) and str(edge.get("to")) == str(nxt):
            edge_paces = WALK_EDGE_PACES.get(
                str(edge.get("distance") or "").strip().casefold())
            break
    # A ROOM IS A ROOM EVEN WHEN NOBODY MEASURED IT (the owner, twice:
    # "ten minutes is still quite too long to cross a single room").
    #
    # The first cut of this kept the old flat rate wherever a room carried no
    # `extent`, to protect a town fixture whose one-hour window buys six
    # streets. That was protecting a TEST rather than a truth: no room takes
    # ten minutes to walk through, measured or not, and a size tier is a
    # perfectly good statement of how big a room is -- the light and sound
    # fields have read tiers as geometry all along.
    #
    # So the span always decides, and what a LONG link costs is said by the
    # edge, which is what `distance` is for and what the plan schema already
    # asks for: `far` and `remote` are "more than one beat to cross". A town
    # whose places are a walk apart says so on the edge; a corridor does not
    # have to say anything to stop costing what a road costs.
    try:
        paces = float(room_span(scene, str(here)))
    except Exception:
        paces = 0.0
    paces += WALK_EDGE_PACES["adjacent"] if edge_paces is None else edge_paces
    return max(1.0, min(town, paces / WALK_PACES_PER_SECOND))


def edge_cost(scene, here, nxt) -> float:
    """The same crossing as a fraction of the credit `WALK_ROOMS_PER_HOUR`
    buys, so the walk's arithmetic is untouched and only the PRICE moves."""
    return edge_seconds(scene, here, nxt) / (3600.0 / WALK_ROOMS_PER_HOUR)


def _roll(key, seed):
    """Deterministic 0..1 from ``(key, seed)``, safe for THRESHOLD selection.

    Not the ``crc32(key|seed)`` idiom the tie-breaks use, and the difference
    is load-bearing: crc32 is linear over GF(2), so ``crc(key|7)`` and
    ``crc(key|8)`` differ by one constant XOR across every same-length key —
    measured, adjacent seeds selected the identical first ten bodies, and a
    per-window "rotation" whose windows all pick the same people is not one.
    A tie-break only needs any stable total order, so linearity is harmless
    there; a membership test under a threshold needs the seed to actually
    decorrelate draws, so the seed is folded in multiplicatively and the
    result finalized (murmur3's mixer). Never ``hash()`` — Python salts it
    per process, and a checkpoint restore is a different one.
    """
    mixed = (zlib.crc32(str(key).encode("utf-8"))
             ^ (int(seed) * 0x9E3779B9)) & 0xFFFFFFFF
    mixed = (mixed * 0x85EBCA6B) & 0xFFFFFFFF
    mixed ^= mixed >> 13
    mixed = (mixed * 0xC2B2AE35) & 0xFFFFFFFF
    mixed ^= mixed >> 16
    return mixed / 0xFFFFFFFF


# ------------------------------------------------------------------ the walk

def en_route(body):
    """Is this body mid-walk: carrying a route it has not reached the end of."""
    rec = (body or {}).get("walk")
    if not isinstance(rec, dict):
        return False
    route = rec.get("route") or []
    return len(route) > 1 and int(rec.get("leg") or 0) < len(route) - 1


def _dispatch(body, target, scene, cache, hours, neighbors=None):
    """Put ``body`` on a route to ``target``. Returns the body, or ``None``
    when there is no route (the caller leaves it where it stands: a
    charter's mistake must not be laundered into a movement).

    A body already walking to this target keeps its route and its credit --
    it was advanced this window by `continue_walks` and is not paid twice. A
    body walking somewhere ELSE is re-dispatched from where it stands, which
    is a new destination rather than a re-plan around a block: the watch
    changed, and the body turns. Its unspent credit for this window carries.
    """
    origin = str(body.get("place") or "")
    current = body.get("walk") if isinstance(body.get("walk"), dict) else None
    if current and str(current.get("target") or "") == target:
        return body
    # PLANNED ON THE GRAPH THE BODY WALKS, which is the same one `_advance`
    # re-checks each leg against. A creature that can open doors decides on
    # a wider graph than `passable_path`'s, and planning on the narrower one
    # dropped the move silently.
    route = walk_route(scene, origin, target, cache=cache,
                       neighbors=neighbors) if scene else None
    if scene and route is None:
        return None
    if not scene:
        # No graph: the institution is one place and the walk is a step.
        route = [origin, target] if origin != target else [origin]
    credit = float(current.get("credit") or 0.0) if current \
        else float(hours) * WALK_ROOMS_PER_HOUR
    body = dict(body)
    body["walk"] = {"target": target, "route": route, "leg": 0,
                    "credit": credit, "held": False}
    return body


def _advance(body_key, body, neighbors, travelled, walked, scene=None):
    """Spend the walk's credit one edge at a time. Mutates ``travelled`` and
    ``walked``; returns the body, with the walk record dropped on arrival.

    Each edge is re-checked against ``neighbors`` (`passable_neighbors`, the
    same graph the route was planned on), so a door shut since dispatch HOLDS
    the body where it is -- this window and every window until it opens --
    and it is not rerouted. ``neighbors`` of ``None`` means no graph to check
    against (the no-scene institution), and every edge passes.
    """
    rec = body.get("walk")
    if not isinstance(rec, dict):
        return body
    route = [str(r) for r in rec.get("route") or []]
    leg = max(0, int(rec.get("leg") or 0))
    credit = float(rec.get("credit") or 0.0)
    held = False
    own = None
    while leg + 1 < len(route):
        here, nxt = route[leg], route[leg + 1]
        # WHAT THIS LEG COSTS, from the room it crosses (`edge_cost`), rather
        # than one flat room-per-street. Checked before the credit so a body
        # that cannot yet afford the leg simply keeps its credit.
        price = edge_cost(scene, here, nxt) if scene is not None else 1.0
        if credit < price:
            break
        if neighbors is not None and nxt not in (neighbors.get(here) or ()):
            held = True
            break
        leg += 1
        credit -= price
        travelled[body_key] = travelled.get(body_key, 0) + 1
        if own is None:
            # Copy-on-write, per body that actually moves: the caller's
            # `walked` is shared by reference and only a mover's own map
            # is duplicated. A whole-record deep copy per window measured
            # as most of the walk's cost on the 300-body town (77s against
            # 53s for the same 64,035 rooms), because the record grows
            # with every window while the movers per window do not.
            own = {a: dict(b) for a, b in (walked.get(body_key) or {}).items()}
            walked[body_key] = own
        edges = own.setdefault(here, {})
        edges[nxt] = int(edges.get(nxt) or 0) + 1
    body = dict(body)
    was = str(body.get("place") or "")
    body["place"] = route[leg] if route else was
    if body["place"] != was:
        # A within-room station is a fact about ONE room -- an anchor of it,
        # a cell of its grid -- so a leg into another room leaves it behind,
        # exactly as `world.spatial.invalidate_moved_body_cells` drops a
        # scene body's pinned cell on a room change (`charter_place` rule i).
        body.pop("station", None)
    if route and leg == len(route) - 1:
        body.pop("walk", None)
    else:
        body["walk"] = {**rec, "leg": leg, "credit": credit, "held": held}
    return body


def continue_walks(bodies, hours, neighbors=None, travelled=None,
                   walked=None, scene=None):
    """Every body still en route buys this window's rooms and walks on.
    Returns ``(bodies, travelled, walked)``.

    Runs FIRST in the movement phase, before the watch bill posts anybody,
    so a body that was caught in the street at the last window's end
    finishes its walk before it can be sent anywhere new -- and so a body
    re-posted to the place it was already walking to is not paid twice
    (`_dispatch` sees it already bound for the target).

    ONE PRICING REGIME. `relocate` prices every edge at `edge_cost` (the
    doorway's seconds); this took no `scene`, so `_advance` fell back to
    the flat 1.0-room price -- ten minutes a doorway -- for every leg a
    walk carried across a window boundary. Beat windows run 6-45 s, so
    nearly every walk IS a continuation, and a body that would cross a
    corridor in twelve seconds on dispatch took ten minutes over it the
    next beat. The carried-credit cap is in the same units: at most the
    price of the edge the body is standing before, not one flat room.
    """
    bodies = {k: dict(v) for k, v in (bodies or {}).items()}
    travelled = dict(travelled or {})
    walked = dict(walked or {})   # shallow; `_advance` copies a mover's own
    allowance = max(0.0, float(hours)) * WALK_ROOMS_PER_HOUR
    for key in sorted(bodies):
        body = bodies[key]
        if not en_route(body) or not body.get("available"):
            continue
        rec = dict(body["walk"])
        # A held body does not bank rooms: the remainder of an edge carries
        # (as the courier's `moved_at` carries), a window spent at a shut
        # door does not, or the body would sprint the day it opened.
        route = [str(r) for r in rec.get("route") or []]
        leg = max(0, int(rec.get("leg") or 0))
        cap = 1.0
        if scene is not None and leg + 1 < len(route):
            cap = edge_cost(scene, route[leg], route[leg + 1])
        rec["credit"] = min(float(rec.get("credit") or 0.0), cap) + allowance
        body = dict(body, walk=rec)
        bodies[key] = _advance(key, body, neighbors, travelled, walked, scene)
    return bodies, travelled, walked


def relocate(bodies, watch, posts, scene, travelled=None, hours=4.0,
             neighbors=None, walked=None, cache=None):
    """Send the posted bodies toward their posts and walk them as far as the
    window pays for. Returns ``(bodies, travelled, walked)``.

    ``travelled`` accumulates rooms actually crossed per body across the whole
    run — a diagnostic and a story hook. ``walked`` is the record that
    matters: ``{body: {from_room: {to_room: crossings}}}``, every edge a body
    has walked, in room-id vocabulary, which is what a promotion can hand over
    as earned routes (`charter_promote.inherited_place_graph`).
    """
    moves = {}
    for post_key, body_key in sorted((watch or {}).items()):
        body = (bodies or {}).get(body_key)
        post = (posts or {}).get(post_key)
        if body is None or post is None or not post.get("place"):
            continue
        moves[body_key] = str(post["place"])
    return walk(bodies, moves, scene, travelled, cache=cache, hours=hours,
                neighbors=neighbors, walked=walked)


def _nearest(reach, key, places, seed):
    """The closest of ``places`` this body can reach, or ``None``.

    TIES ARE BROKEN BY THE BODY, NOT BY THE ROOM'S NAME. The first version
    took ``min((rooms, place))``, so where two candidates were the same
    distance the room id decided -- and on a hub-and-spoke graph, which is
    what a hull or a settlement round a square actually is, EVERY distance
    ties. Measured on chat 98's recorded charter with the run's hand-added
    upkeep removed: every errand at seeds 3, 4 and 5 went to `arboretum`,
    the alphabetically first workroom, and a population that all walks to
    one room has not circulated. The roll is the same deterministic mixer
    the selection above uses, folded with the place, so a replay under one
    seed is identical and adjacent seeds decorrelate.
    """
    best = None
    for place in places:
        rooms = (reach or {}).get((key, str(place)))
        if rooms is None:
            continue
        candidate = (int(rooms), _roll(f"{key}|{place}", seed), str(place))
        if best is None or candidate < best:
            best = candidate
    return best[2] if best else None


def errands(bodies, needs, upkeeps, watch, places, reach, seed=0,
            rate=ERRAND_RATE, hours=4.0, commons=(), phase=None):
    """Who goes where this window, off the watch bill. ``{body: place}``.

    THE DAY DECIDES WHETHER ANYONE GOES OUT. ``phase`` is the window's phase
    of the day (`world/day_cycle.charter_phase`, None for an institution the
    story has not told when it is): in the resting phases nobody runs an
    errand, so everyone off the watch walks home through `homecomings` and
    the town sleeps in its berths; in the social phases a body goes out only
    for its own sake -- to a commons, the tavern rather than the granary --
    and a charter with no commons keeps its people home. No phase is the
    day as it was before the cycle: errands at every hour.

    THE CIRCULATION THE RUMOUR CHANNEL WAS MISSING, and the measurement
    that demanded it: a famine month minted 244 witnessable news events and
    the second-hand spread of every one of them was ZERO — then, with the
    tell rule fixed to prefer absent subjects, ONE. The cause was never the
    telling: apart from the half-dozen posted bodies, nobody ever left the
    room they were authored into, so every room was an island and a witness
    only ever talked to co-witnesses. A world without circulation cannot
    have rumour, whatever its gossip machinery deserves.

    An errand is the cheapest honest version of a life's traffic: a body
    visits the place its own needs are fed from — the condition its
    ``fed_by`` names, which is the supply chain saying WHERE the bread is —
    or, lacking one, the nearest place it may go FOR ITS OWN SAKE
    (``commons``, from `charter_space.commons_places`), and only failing
    that its nearest charter place. Seeded rotation, off-duty and able
    bodies only, and it moves them through the same machinery the watch
    bill uses: real positions, real distance, no state but the position
    everything else already carries.

    THE ORDER IS THE RULE, and it is what the commons is for: a body off the
    watch is not going to work, so a room that answers to no post outranks
    one that does whenever nothing is pulling the body anywhere. A charter
    that names no commons keeps exactly the behaviour it had — the fallback
    is still its charter places — which is what stops the widening from
    becoming a requirement on every institution already written.

    A body still walking somewhere is not sent on an errand: it is already
    going somewhere, and it arrives before it is asked again.
    """
    posted = set((watch or {}).values())
    out = {}
    chance = min(1.0, float(rate) * max(0.0, float(hours)))
    if chance <= 0.0:
        return out
    from .day_cycle import RESTING_PHASES, SOCIAL_PHASES
    if phase in RESTING_PHASES:
        return out
    social = phase in SOCIAL_PHASES
    for key in sorted(bodies or {}):
        body = bodies[key]
        if key in posted or not body.get("available") or en_route(body):
            continue
        if _roll(key, seed) >= chance:
            continue
        target = None
        if social:
            target = _nearest(reach, key, commons or (), seed)
            if target is not None:
                out[key] = target
            continue
        held = (needs or {}).get(key) or {}
        fed = [(float(n.get("level", 1.0)), str(n.get("fed_by")))
               for n in held.values() if n.get("fed_by")]
        for _level, upkeep_key in sorted(fed):
            place = str((upkeeps or {}).get(upkeep_key, {})
                        .get("place") or "")
            if place and (key, place) in (reach or {}):
                target = place
                break
        if target is None:
            target = _nearest(reach, key, commons or (), seed) \
                or _nearest(reach, key, places or (), seed)
        if target is not None:
            out[key] = target
    return out


def walk(bodies, moves, scene, travelled=None, cache=None, hours=4.0,
         neighbors=None, walked=None):
    """Apply ``{body: place}`` moves. Returns ``(bodies, travelled, walked)``.

    The one generic mover: postings, errands and homecomings all go through
    it, so a visit costs the same bookkeeping a posting does and no position
    is ever written by anything that did not walk there. Each body is put on
    a route (`_dispatch`) and walked as far as this window's credit reaches
    (`_advance`); the walk record survives on the body until it arrives.
    ``cache`` is the ``(origin, target) -> route`` dict `walk_route` shares
    -- for a fixed scene a path never changes, so a run pays for each pair
    once.
    """
    bodies = {k: dict(v) for k, v in (bodies or {}).items()}
    travelled = dict(travelled or {})
    walked = dict(walked or {})   # shallow; `_advance` copies a mover's own
    cache = {} if cache is None else cache
    for body_key in sorted(moves or {}):
        body = bodies.get(body_key)
        target = str((moves or {}).get(body_key) or "")
        if body is None or not target or not body.get("available"):
            continue
        if str(body.get("place") or "") == target and not en_route(body):
            continue
        dispatched = _dispatch(body, target, scene, cache, hours, neighbors)
        if dispatched is None:
            continue
        bodies[body_key] = _advance(body_key, dispatched, neighbors,
                                    travelled, walked, scene)
    return bodies, travelled, walked


def homecomings(bodies, watch, visits):
    """``{body: berth}`` for everyone with nowhere else to be.

    The other half of an errand: a body neither posted nor visiting walks
    back to its own berth rather than living forever wherever the last
    window left it. Costs nothing for the common case — a body already home
    is not a move. A body still on its way somewhere is not sent home from
    the street.
    """
    posted = set((watch or {}).values())
    out = {}
    for key in sorted(bodies or {}):
        body = bodies[key]
        if key in posted or key in (visits or {}) or en_route(body):
            continue
        berth = str(body.get("berth") or "")
        if berth and str(body.get("place") or "") != berth:
            out[key] = berth
    return out


# ------------------------------------------------- the scene's own movement

def place_body(registry, charter_key, body_key, room):
    """The SCENE moved this body: land it. Returns the registry (mutated).

    Not `relocate`/`walk`, on purpose. Those dispatch a body along a route
    the charter planned and pay for it window by window; a Director
    `positions` entry naming a townsperson is a fact the beat already
    resolved -- she is in the next room NOW -- so nothing is walked and no
    route may compete with what the scene just did: the walk (and the errand
    riding it) is dropped and the body stands where the scene put it. The
    station goes with it, as on every other `place` write (`_advance`): an
    anchor or a cell of the old room names nothing in the new one. The
    charter stays the ONE owner of `place` -- the scene keeps no positions
    row for an unpromoted body (`world/charter_place.py`).

    The authoring seam the World Browser's map will call to drag a body
    between rooms (`docs/UNBUILT.md`, the charter-placement follow-up); the
    commit reaches it through `charter_runtime.apply_scene_placements`.
    """
    item = ((registry or {}).get("items") or {}).get(str(charter_key))
    body = ((item or {}).get("state") or {}).get("bodies", {}).get(str(body_key)) \
        if item else None
    if body is None:
        return registry
    room = str(room or "")
    if room and room != str(body.get("place") or ""):
        body["place"] = room
        body.pop("station", None)
    body.pop("walk", None)
    body.pop("errand", None)
    return registry


def station_body(registry, charter_key, body_key, station):
    """Where in its place this body stands, authored: ``{"at": anchor}`` or
    ``{"cell": [x, y]}``, optionally with ``near`` and ``facing``
    (`charter_model.normalize_body_station`); ``None`` clears it and the
    body falls back to the post's anchor or its dealt cell
    (`world/charter_place.py` rules ii/iv). Returns the registry (mutated).

    The within-room half of the authoring seam `place_body` is the room half
    of; the map's drop onto a cell or a fixture lands here."""
    from .charter_model import normalize_body_station

    item = ((registry or {}).get("items") or {}).get(str(charter_key))
    body = ((item or {}).get("state") or {}).get("bodies", {}).get(str(body_key)) \
        if item else None
    if body is None:
        return registry
    normalized = normalize_body_station(station) if body.get("place") else None
    if normalized:
        body["station"] = normalized
    else:
        body.pop("station", None)
    return registry


def furthest_travelled(travelled, limit=5):
    """The bodies that have covered the most ground, most first."""
    return sorted((travelled or {}).items(),
                  key=lambda kv: (-int(kv[1]), kv[0]))[:limit]


def walked_edges(walked, body_key):
    """The edges one body has walked, as ``[(from_room, to_room, crossings)]``
    -- the promotion-facing read of the record `relocate`/`walk` keep."""
    out = []
    for origin, ends in ((walked or {}).get(body_key) or {}).items():
        for end, count in (ends or {}).items():
            out.append((str(origin), str(end), int(count)))
    return sorted(out)
