"""What one beat pays to ask a room its exposure (review 2026-09-07, C17).

`world.weather.room_exposure` is asked the same room many times in a single
beat: every reader that cares whether the sky reaches a place -- the ground
ledger, the light field, the sound and scent fields, the backdrop prompt --
asks it, and `weather_depth`'s graph walk asks it once per node it visits, per
room it is asked about. Each ask casefolds the room's name and description and
scans roughly 110 keywords over the result.

This measures the two halves the finding names, on a REAL stored scene:

  * `room_exposure` calls and wall clock for one `weather_for_room` pass over
    every room in the scene (the shape `_advance_ground` produces on a wet
    beat, and the shape the backdrop/ambience readers produce on any beat);
  * the same for `persist.commit._advance_ground` itself.

It also dumps the derived answers, so a speed-up can be proved to be one:
run with `--dump before.json`, change the code, run with `--dump after.json`,
and `diff` the two. Nothing here writes to the database -- it is opened
read-only and only the `world` row holding the scene is read.

Usage (`ENGINE_DB` is only read for the story's weather severity, and must
name an INITIALISED database -- a throwaway one is fine, and is what you
want, since the whole point is not to touch the story copy):

    ENGINE_DB=/tmp/scratch.db .venv/bin/python \\
        tools/bench/bench_room_exposure.py \\
        --db /path/to/copy-of-a-story.db --chat 117 --dump /tmp/before.json

`--weather rain` grafts a falling-precipitation weather blob onto the scene in
memory (the database is untouched), because a scene stored on a dry beat exits
`weather_for_room` before it reaches the exposure walk at all, and the wet path
is the one the finding is about.
"""
import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

import world.weather as weather  # noqa: E402
from persist.commit import _advance_ground  # noqa: E402

#: The weather a dry stored scene is measured under with `--weather rain`.
#: Every value is from the closed vocabulary `world.weather` already enforces.
_RAIN = {"sky": "overcast", "precipitation": "rain", "intensity": "moderate",
         "wind": "breeze", "temperature": "mild", "thundersnow": False}


def load_scene(path, chat_id):
    """The stored scene blob for one chat, read-only."""
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        row = con.execute(
            "SELECT value FROM world WHERE chat_id=? AND key='scene'",
            (chat_id,)).fetchone()
    finally:
        con.close()
    if not row:
        raise SystemExit("no scene stored for chat %s in %s" % (chat_id, path))
    return json.loads(row[0])


class _Counter:
    """Counts `room_exposure` calls without changing what it answers."""

    def __init__(self):
        self.calls = 0
        self._real = weather.room_exposure

    def __enter__(self):
        def counted(scene, room_id):
            self.calls += 1
            return self._real(scene, room_id)
        weather.room_exposure = counted
        return self

    def __exit__(self, *exc):
        weather.room_exposure = self._real


def answers(scene):
    """Everything the exposure derivation is asked for, per room, sorted."""
    out = {}
    for room_id in sorted((scene.get("rooms") or {})):
        out[room_id] = {
            "exposure": weather.room_exposure(scene, room_id),
            "depth": weather.weather_depth(scene, room_id),
            "weather": weather.weather_for_room(scene, room_id),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="a COPY of a story database")
    ap.add_argument("--chat", type=int, required=True)
    ap.add_argument("--weather", choices=("stored", "rain"), default="rain")
    ap.add_argument("--repeats", type=int, default=5,
                    help="timed passes; the reported time is the fastest")
    ap.add_argument("--dump", default="",
                    help="write the derived answers here, to diff across a change")
    args = ap.parse_args()

    scene = load_scene(args.db, args.chat)
    if args.weather == "rain":
        scene["weather"] = dict(_RAIN)
    rooms = list(scene.get("rooms") or {})
    print("chat %s: %d rooms, weather %s"
          % (args.chat, len(rooms), scene.get("weather")))

    # Warm every lazy import the walk reaches for, so the first timed pass is
    # measuring the walk and not `world.spatial` being imported.
    answers(scene)

    with _Counter() as counter:
        for room_id in rooms:
            weather.weather_for_room(scene, room_id)
        print("weather_for_room over every room: %d room_exposure calls"
              % counter.calls)

    best = min(_time(lambda: [weather.weather_for_room(scene, r) for r in rooms])
               for _ in range(args.repeats))
    print("weather_for_room over every room: %.2f ms" % (best * 1000))

    ground = dict(scene)
    best = min(_time(lambda: _advance_ground(args.chat, dict(ground)))
               for _ in range(args.repeats))
    print("_advance_ground on the same scene: %.2f ms" % (best * 1000))

    dry = dict(scene)
    dry["weather"] = {"precipitation": "none"}
    dry.pop("ground", None)
    best = min(_time(lambda: _advance_ground(args.chat, dict(dry)))
               for _ in range(args.repeats))
    print("_advance_ground, dry and no ground ledger: %.3f ms" % (best * 1000))

    if args.dump:
        with open(args.dump, "w") as fh:
            json.dump(answers(scene), fh, indent=1, sort_keys=True)
        print("answers written to %s" % args.dump)


def _time(fn):
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


if __name__ == "__main__":
    main()
