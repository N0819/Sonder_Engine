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

from .charter_space import travel_rooms


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


def furthest_travelled(travelled, limit=5):
    """The bodies that have covered the most ground, most first."""
    return sorted((travelled or {}).items(),
                  key=lambda kv: (-int(kv[1]), kv[0]))[:limit]
