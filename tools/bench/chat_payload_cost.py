"""What one open of a story costs: queries, row bytes, payload bytes, wall.

The transcript read is the part of `GET /api/chats/{cid}` that grows with the
length of a story, and it is on the two paths a reader hits most -- opening a
story, and the refresh that follows every finished beat. This measures both
shapes of that call against a COPY of a real database:

  * the whole payload, which is what opening a story asks for;
  * `?since_turn_id=` at the last turn, which is what the page asks for after
    a beat commits (`static/js/chat.js`, `openChat(id, {sinceTurnId})`).

Run it against a copy, never a live `engine.db` -- it opens the file through
`core.db` and a stray write would land in the story:

    ENGINE_DB=/path/to/copy.db PYTHONPATH=. \\
        python tools/bench/chat_payload_cost.py 114 117

Reading the output: `queries` must not grow with `turns` (review 2026-09-07,
C22 -- it used to, one steps/variants read per beat), and the `since` row is
what a page is spared on every beat of a long story. Measured on the review's
bench copies, 2026-09-07: chat 117 at 124 turns went from 149 queries /
266,689 payload bytes to 25 / 266,689 whole, and 25 / 32,209 sliced.
"""

from __future__ import annotations

import json
import sys
import time

import core.db as db

REPS = 15


def _instrument():
    """Count queries and the bytes their rows carry, wherever `q` is spelled.

    Every module binds `q` by `from core.db import q`, so the counter has to
    replace the name in each module that already imported it as well as on
    `core.db` itself; a module imported later picks up the patched original.
    """
    original = db.q
    stats = {"queries": 0, "row_bytes": 0}

    def counting(sql, args=(), one=False):
        rows = original(sql, args, one)
        stats["queries"] += 1
        for row in ([] if rows is None else ([rows] if one else rows)):
            for value in tuple(row):
                if isinstance(value, str):
                    stats["row_bytes"] += len(value.encode())
                elif isinstance(value, (bytes, bytearray)):
                    stats["row_bytes"] += len(value)
        return rows

    db.q = counting
    for module in list(sys.modules.values()):
        if module is not None and getattr(module, "q", None) is original:
            module.q = counting
    return stats


def _measure(call, stats):
    call()  # warm: the first read pays for page cache and lazy imports
    stats["queries"] = stats["row_bytes"] = 0
    times = []
    for _ in range(REPS):
        started = time.perf_counter()
        payload = call()
        times.append(time.perf_counter() - started)
    times.sort()
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return {
        "turns": len(payload["turns"]),
        "queries": stats["queries"] // REPS,
        "row_bytes": stats["row_bytes"] // REPS,
        "payload_bytes": len(blob.encode()),
        "median_ms": round(times[len(times) // 2] * 1000, 3),
    }


def main(chat_ids):
    stats = _instrument()
    from core.db import q as _q  # after the patch, so this is the counter
    import web.app as app

    for cid in chat_ids:
        turns = _q("SELECT id FROM turns WHERE chat_id=? ORDER BY idx", (cid,))
        if not turns:
            print(json.dumps({"chat": cid, "error": "no turns"}))
            continue
        since = turns[-2]["id"] if len(turns) > 1 else turns[-1]["id"]
        whole = _measure(lambda: app.chat_get(cid), stats)
        sliced = _measure(lambda: app.chat_get(cid, since), stats)
        print(json.dumps({"chat": cid, "whole": whole,
                          "since_turn_id": since, "sliced": sliced}))


if __name__ == "__main__":
    ids = [int(a) for a in sys.argv[1:]]
    if not ids:
        raise SystemExit(__doc__)
    main(ids)
