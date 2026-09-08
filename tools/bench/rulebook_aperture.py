"""What the rulebook's charter walk costs, and what its aperture misses.

Review 2026-09-07 finding C18. `agents/mapping.rulebook_rows` used to walk
the first `RULEBOOK_ROOMS_CAP` = 24 keys of ``scene["rooms"]`` in DICT ORDER
to find the creatures and institutions "in view", while `director_resolve`
derived the beat's real aperture -- the player's room, its ambient scope, and
a declared destination -- and walked `present_charter_figures` over it a
second time. This measures both halves on a story's own charter:

  * how many rooms each walk covers, and whether the retired dict-order cap
    would have omitted the room the player is standing in;
  * the wall clock of `present_charter_figures` over each set, and how it
    grows with the number of rooms walked (the town's charter is read once
    per beat per set, so a second set is a second read).

Run it against a COPY of a database, never a live one::

    PYTHONPATH=. python tools/bench/rulebook_aperture.py /path/to/copy.db 114

It only reads: no model call, no write, no beat.
"""

from __future__ import annotations

import os
import sys
import time

#: The cap this finding retired, kept here only so the bench can show what it
#: would have covered. Nothing in the engine reads it any more.
RETIRED_ROOMS_CAP = 24


def _timed(fn, repeat=5):
    fn()
    started = time.perf_counter()
    out = None
    for _ in range(repeat):
        out = fn()
    return (time.perf_counter() - started) / repeat, out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    path, cid = argv[1], int(argv[2])
    os.environ["ENGINE_DB"] = path
    from core import db

    db.configure(path)
    from agents.common import present_charter_figures
    from core.db import q, wget
    from world.charter_runtime import registry_for
    from world.spatial import ambient_scope

    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        print("no chat %d in %s" % (cid, path))
        return 1
    scene = wget(cid, "scene", {}) or {}
    rooms = list((scene.get("rooms") or {}).keys())
    registry = registry_for(cid, None) or {}
    items = registry.get("items") or {}
    bodies = sum(len((i.get("state") or {}).get("bodies") or {})
                 for i in items.values())
    places = sorted({str(b.get("place") or "")
                     for i in items.values()
                     for b in ((i.get("state") or {}).get("bodies") or {}).values()
                     if b.get("place")})
    print("chat %d: %d scene rooms, %d charters, %d bodies, %d charter places"
          % (cid, len(rooms), len(items), bodies, len(places)))

    from story.scene import persona_name, persona_of

    _pers = persona_of(dict(chat)) or {}
    p_name = _pers.get("name") or persona_name(_pers) or ""
    p_room = str((scene.get("positions") or {}).get(p_name) or "")
    view = set()
    if p_room:
        view.add(p_room)
        nearby, _ = ambient_scope(scene, p_room)
        view.update(str(r) for r in (nearby or ()) if r)
    capped = rooms[:RETIRED_ROOMS_CAP]
    print("player %r in %r" % (p_name, p_room))
    print("retired dict-order walk: %d rooms; aperture: %d rooms"
          % (len(capped), len(view)))
    if p_room and p_room not in capped:
        print("  !! the retired cap OMITS the player's own room")

    t_cap, figs_cap = _timed(
        lambda: present_charter_figures(cid, scene, capped))
    t_view, figs_view = _timed(
        lambda: present_charter_figures(cid, scene, view))
    print("present_charter_figures(dict-order %d rooms): %.4fs, %d figures"
          % (len(capped), t_cap, len(figs_cap)))
    print("present_charter_figures(aperture %d rooms):   %.4fs, %d figures"
          % (len(view), t_view, len(figs_view)))

    # How the walk grows with the rooms handed to it, over this story's own
    # charter places -- the shape a >24-room plan pays twice when two stages
    # each derive their own set.
    for n in (1, 4, 8, 16, 24, 40):
        sample = places[:n]
        if not sample:
            break
        seconds, figs = _timed(
            lambda: present_charter_figures(cid, scene, sample))
        print("  %2d charter places: %.4fs, %d figures"
              % (len(sample), seconds, len(figs)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
