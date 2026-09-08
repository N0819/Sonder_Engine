"""Every stored sky's answers, before and after the weather axes (A88).

Review 2026-09-07 A88 replaced weather's closed Earth vocabulary with a NAME
the story owns plus AXES the engine owns. The ruling's own requirement was
that "every existing story's stored weather stays readable -- a stored Earth
word maps to its axes once, at read", so the change has to be provably
answer-preserving on real data everywhere except the drift, which is the part
it deliberately fixes.

This dumps, for every stored scene in a database copy, exactly the answers a
beat reads off the weather:

  * `normalize_weather` on the stored record;
  * per room: `weather_for_room`, both channels of `weather_words`,
    `room_exposure`, `ground_after` and `has_lightning`;
  * `day_cycle.sun_light` at every phase;
  * `advance_weather` at five drift windows.

Run it on the OLD revision with `--dump before.json`, on the NEW one with
`--dump after.json`, and `--compare before.json after.json` to see what moved.
The comparison folds list indices out of the path, so the report is one line
per differing FIELD with a count and an example rather than thousands of rows.

Measured 2026-09-08 over both bench copies (213 stored scene blobs, 24 of them
carrying weather): outside the drift, the only differences are the new axis
keys appearing and `thundersnow` folding into `electrical` -- every composed
word, exposure, ground state, lightning verdict and sun-light answer identical.
Inside the drift, over 96 windows, the OLD table invented a fall over a dry sky
13 times and replaced the story's own declared fall with a different one 29
more; the new drift kept the declared fall in all 96.

Nothing here writes to the database: it is opened read-only through a `file:`
URI and only the `world` rows holding a scene are read.

Usage:

    .venv/bin/python tools/bench/weather_axes_parity.py \\
        --db /path/to/copy-of-a-story.db --dump /tmp/after.json
    .venv/bin/python tools/bench/weather_axes_parity.py \\
        --compare /tmp/before.json /tmp/after.json
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from world import weather as W                                    # noqa: E402
from world.day_cycle import SUN_LIGHT, sun_light                   # noqa: E402

#: The drift windows sampled, in in-story hours. Five is enough to show a sky
#: moving without turning the dump into a simulation log.
WINDOWS = (0, 1, 2, 5, 24)


def snapshot(paths):
    out = []
    for path in paths:
        connection = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
        rows = connection.execute(
            "SELECT rowid, value FROM world WHERE key='scene' ORDER BY rowid"
        ).fetchall()
        for rowid, value in rows:
            try:
                scene = json.loads(value)
            except (TypeError, ValueError):
                continue
            if not isinstance(scene, dict):
                continue
            stored = scene.get("weather")
            record = {
                "db": os.path.basename(path),
                "rowid": rowid,
                "stored": stored,
                "normalized": W.normalize_weather(stored),
                "rooms": {},
            }
            for room_id in sorted(scene.get("rooms") or {}):
                scoped = W.weather_for_room(scene, room_id)
                exposure = W.room_exposure(scene, room_id)
                record["rooms"][room_id] = {
                    "scoped": scoped,
                    "sight": W.weather_words(scoped, "sight"),
                    "sound": W.weather_words(scoped, "sound"),
                    "exposure": exposure,
                    "ground": W.ground_after(
                        (scene.get("ground") or {}).get(room_id), scoped,
                        "seasonal", exposed=exposure == "open"),
                    "lightning": W.has_lightning(scoped),
                }
            # SIGNATURE-AGNOSTIC, so the before column is what that
            # revision's engine actually answered: `sun_light` took a sky
            # NAME before A88 and takes the whole record after it. Measuring
            # the old function with the new convention printed 18 false
            # differences (6 scenes x 3 phases) while the real answer is
            # identical -- 192 comparisons, 0 differences.
            _rec = W.normalize_weather(stored) or None
            def _sun(phase, rec=_rec):
                try:
                    return sun_light(phase, rec)
                except Exception:
                    return sun_light(phase, (rec or {}).get("sky"))
            record["sun"] = {phase: _sun(phase) for phase in sorted(SUN_LIGHT)}
            record["drift"] = [
                W.advance_weather(stored, hours * 3600, "seed-%d" % rowid)
                for hours in WINDOWS]
            out.append(record)
        connection.close()
    return out


def _walk(before, after, path, counts, samples):
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            _walk(before.get(key, "<absent>"), after.get(key, "<absent>"),
                  path + "." + str(key), counts, samples)
        return
    if isinstance(before, list) and isinstance(after, list) \
            and len(before) == len(after):
        for index, (left, right) in enumerate(zip(before, after)):
            _walk(left, right, "%s[%d]" % (path, index), counts, samples)
        return
    if before != after:
        # Fold room ids and list indices out, so the report is one line per
        # FIELD rather than one per stored blob.
        key = ".".join(part for part in path.split(".")
                       if not part.isdigit())
        counts[key] += 1
        samples.setdefault(key, (before, after))


def compare(before_path, after_path):
    before = json.load(open(before_path, encoding="utf-8"))
    after = json.load(open(after_path, encoding="utf-8"))
    if len(before) != len(after):
        print("different blob counts: %d vs %d" % (len(before), len(after)))
        return
    counts: collections.Counter = collections.Counter()
    samples: dict = {}
    for left, right in zip(before, after):
        for section in ("normalized", "sun", "drift", "rooms"):
            _walk(left.get(section), right.get(section), section, counts,
                  samples)
    for key, count in counts.most_common():
        print("%6d  %s  %s" % (count, key,
                               json.dumps(samples[key], ensure_ascii=False)[:160]))
    print("total differing leaves:", sum(counts.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", action="append", default=[],
                        help="a read-only copy of a story database")
    parser.add_argument("--dump", help="write the snapshot here as JSON")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args()
    if args.compare:
        compare(*args.compare)
        return
    if not args.db:
        parser.error("--db is required unless --compare is given")
    records = snapshot(args.db)
    text = json.dumps(records, sort_keys=True, ensure_ascii=False, indent=1)
    if args.dump:
        with open(args.dump, "w", encoding="utf-8") as handle:
            handle.write(text)
        weathered = sum(1 for record in records if record["normalized"])
        print("%d scene blobs, %d carrying weather -> %s"
              % (len(records), weathered, args.dump))
    else:
        print(text)


if __name__ == "__main__":
    main()
