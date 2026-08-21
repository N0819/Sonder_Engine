"""Bodies going to the posts they were given, and the ground that costs.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §3. Until now a body had a
``place`` and stayed in it forever: reach constrained who COULD be posted and
nobody ever actually went. That is a watch bill nobody stands, and it also
quietly froze everything downstream — the same faces met in the same rooms
every window, so gossip could only ever circulate within a berth.

Movement is the cheapest possible version of itself and deliberately so. A
body assigned a post is AT that post for the window; the rooms between are
counted as distance travelled and are not otherwise simulated. Whether
somebody is seen in a corridor on the way is the scene's business, not the
charter's, and inventing a per-room walk here would be a second movement
system competing with the one `world.spatial` already owns.

WHAT IT UNLOCKS, which is more than it costs:

  * **Distance is a real quantity per body**, so "who moves the most" has an
    answer and the answer means something.
  * **Co-presence changes**, so who talks to whom changes, so belief spreads
    along the paths people actually walk rather than pooling in berths.
  * **Reach is recomputed when it matters** — `charter_run` already guards for
    a body's place changing, and until now that guard never fired once.
"""

from __future__ import annotations

import zlib

from .charter_space import travel_rooms

#: Chance per HOUR that an off-duty body goes somewhere — per hour, not per
#: window, because every other rate in this package is per hour and a rate
#: whose unit quietly depends on the caller's window size is an authored
#: number that fails silently (the first version was per-window, and the
#: same charter circulated four times harder at one-hour windows than at
#: four). ~0.24 per four-hour window: one or two outings a day. A charter
#: pins its own value (including 0.0, the quiet control) via
#: ``errand_rate``; None means this.
ERRAND_RATE = 0.06


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


def relocate(bodies, watch, posts, scene, travelled=None):
    """Move the posted bodies to their posts. Returns ``(bodies, travelled)``.

    ``travelled`` accumulates rooms crossed per body across the whole run — a
    diagnostic and a story hook rather than state anything reads, which is why
    it is carried separately from the bodies themselves.
    """
    bodies = {k: dict(v) for k, v in (bodies or {}).items()}
    travelled = dict(travelled or {})

    for post_key, body_key in sorted((watch or {}).items()):
        body = bodies.get(body_key)
        post = (posts or {}).get(post_key)
        if body is None or post is None or not post.get("place"):
            continue
        # An absent body does not travel. It was posted from a stale register
        # and it is not going anywhere, which is precisely why the post goes
        # untended and the charter does not find out until somebody looks.
        if not body.get("available"):
            continue
        origin = str(body.get("place") or "")
        target = str(post["place"])
        if origin == target:
            continue
        rooms = travel_rooms(scene, origin, target) if scene else 1
        if rooms is None:
            # Unreachable: it should not have been posted, and the planner's
            # reach filter is what normally prevents this. Leave the body
            # where it is rather than teleporting it — a charter's mistake
            # must not be laundered into a movement.
            continue
        body["place"] = target
        travelled[body_key] = travelled.get(body_key, 0) + int(rooms)
    return bodies, travelled


def errands(bodies, needs, upkeeps, watch, places, reach, seed=0,
            rate=ERRAND_RATE, hours=4.0):
    """Who goes where this window, off the watch bill. ``{body: place}``.

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
    or, lacking one, its nearest charter place, because an institution's
    places are where its people's lives already happen. Seeded rotation,
    off-duty and able bodies only, and it moves them through the same
    machinery the watch bill uses: real positions, real distance, no state
    but the position everything else already carries.
    """
    posted = set((watch or {}).values())
    out = {}
    chance = min(1.0, float(rate) * max(0.0, float(hours)))
    if chance <= 0.0:
        return out
    for key in sorted(bodies or {}):
        body = bodies[key]
        if key in posted or not body.get("available"):
            continue
        if _roll(key, seed) >= chance:
            continue
        target = None
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
            options = [(rooms, place) for (body_key, place), rooms
                       in (reach or {}).items()
                       if body_key == key and place in places]
            if options:
                target = min(options)[1]
        if target is not None:
            out[key] = target
    return out


def walk(bodies, moves, scene, travelled=None, cache=None):
    """Apply ``{body: place}`` moves. Returns ``(bodies, travelled)``.

    The one generic mover: errands and homecomings go through it, so a
    visit costs the same bookkeeping a posting does and no position is ever
    written by anything that did not walk there. ``cache`` is the same
    ``(origin, target) -> rooms`` dict `reach_map` shares — for a fixed
    scene a path never changes, so a run pays for each pair once.
    """
    bodies = {k: dict(v) for k, v in (bodies or {}).items()}
    travelled = dict(travelled or {})
    cache = {} if cache is None else cache
    for body_key in sorted(moves or {}):
        body = bodies.get(body_key)
        target = str((moves or {}).get(body_key) or "")
        if body is None or not target or not body.get("available"):
            continue
        origin = str(body.get("place") or "")
        if origin == target:
            continue
        pair = (origin, target)
        if pair not in cache:
            cache[pair] = travel_rooms(scene, origin, target) if scene else 1
        rooms = cache[pair]
        if rooms is None:
            continue
        body["place"] = target
        travelled[body_key] = travelled.get(body_key, 0) + int(rooms)
    return bodies, travelled


def homecomings(bodies, watch, visits):
    """``{body: berth}`` for everyone with nowhere else to be.

    The other half of an errand: a body neither posted nor visiting walks
    back to its own berth rather than living forever wherever the last
    window left it. Costs nothing for the common case — a body already home
    is not a move.
    """
    posted = set((watch or {}).values())
    out = {}
    for key in sorted(bodies or {}):
        body = bodies[key]
        if key in posted or key in (visits or {}):
            continue
        berth = str(body.get("berth") or "")
        if berth and str(body.get("place") or "") != berth:
            out[key] = berth
    return out


def furthest_travelled(travelled, limit=5):
    """The bodies that have covered the most ground, most first."""
    return sorted((travelled or {}).items(),
                  key=lambda kv: (-int(kv[1]), kv[0]))[:limit]
