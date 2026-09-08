"""What the Charter registry's readers cost per turn, and what they answer.

The C19 sites of the 2026-09-07 review: `presence_view` (which copied a
whole institution twice per voiced presence), and the registry walkers that
rebuilt `charter_identity.display_name` -- and, for three of them,
`identity_aliases` -- for every body on every call.

Two things at once, because a speed-up that changes an answer is a
behaviour change: it TIMES each reader and it DUMPS what each returned, so
two runs of it (before a change and after) can be diffed byte for byte.

    ENGINE_DB=/path/to/copy.db \\
        python tools/bench/charter_identity_index.py <chat id> [out dir]

Point it at a COPY of a story database, never a live one: it opens the file
the engine's own way and reads a real town. It runs no model and writes no
row. Measured on chat 114's four-charter, 66-body town, warm (the second
reader of a turn): presence_view 24.0 ms -> 3.4 ms, charter_speaker_records
30.0 ms -> 0.1 ms, 66 `_body_refs` lookups 440 ms -> 10 ms.
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))


def _presences(runtime, cid):
    """(place, display name) for every unbound body standing somewhere."""
    from world.charter_identity import display_name

    registry = runtime.registry_for(cid)
    out = []
    for _key, item in sorted((registry.get("items") or {}).items()):
        state = item["state"]
        roles = {}
        for post, assigned in (state.get("watch") or {}).items():
            roles.setdefault(str(assigned), []).append(str(post))
        for body_key, body in sorted((state.get("bodies") or {}).items()):
            if body_key in (state.get("bindings") or {}):
                continue
            place = str(body.get("place") or "")
            if place:
                out.append((place, display_name(
                    body, roles.get(body_key) or (), state.get("naming"))))
    return out


def main(argv):
    if not argv or not str(argv[0]).isdigit():
        print(__doc__)
        return 2
    cid = int(argv[0])
    out_dir = argv[1] if len(argv) > 1 else "."
    from core import db
    db.configure(os.environ.get("ENGINE_DB") or db.DB)
    from world import charter_runtime as runtime

    answers, timings = {}, {}

    def timed(label, fn, repeats=3):
        best, value = None, None
        for _ in range(repeats):
            started = time.perf_counter()
            value = fn()
            elapsed = time.perf_counter() - started
            best = elapsed if best is None else min(best, elapsed)
        timings[label] = round(best * 1000.0, 2)
        return value

    present = _presences(runtime, cid)
    started = time.perf_counter()
    for place, name in present:
        answers["presence_view:%s:%s" % (place, name)] = runtime.presence_view(
            cid, place, name)
    timings["presence_view x%d (one pass)" % len(present)] = round(
        (time.perf_counter() - started) * 1000.0, 2)

    places = sorted({place for place, _ in present})
    names = [name for _, name in present]
    registry = runtime.registry_for(cid)
    answers["background_presence_records"] = timed(
        "background_presence_records",
        lambda: runtime.background_presence_records(cid))
    answers["charter_speaker_records"] = timed(
        "charter_speaker_records", lambda: runtime.charter_speaker_records(cid))
    answers["charter_carriers"] = timed(
        "charter_carriers", lambda: runtime.charter_carriers(cid, places))
    answers["carrier_entries"] = timed(
        "carrier_entries", lambda: runtime.carrier_entries(cid))
    answers["charter_dwellings"] = timed(
        "charter_dwellings", lambda: runtime.charter_dwellings(
            cid, sorted(runtime.charter_place_ids(cid))))
    answers["bodies_acting_toward_authored"] = timed(
        "bodies_acting_toward_authored",
        lambda: runtime.bodies_acting_toward_authored(cid, names[:3]))
    answers["registry_warnings"] = timed(
        "registry_warnings", lambda: runtime.registry_warnings(
            registry, cid=cid))

    # The registry itself, last: every reader above is read-only, so this
    # dump has to match the one a run before the change wrote.
    answers["registry"] = runtime.registry_for(cid)
    path = os.path.join(out_dir, "charter_identity_index.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(answers, handle, indent=1, sort_keys=True, default=str)
    for label in sorted(timings):
        print("%-46s %9.2f ms" % (label, timings[label]))
    print("presences: %d; answers written to %s" % (len(present), path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
