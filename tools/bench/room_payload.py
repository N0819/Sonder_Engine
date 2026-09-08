"""What a Writers' Room reply spends rebuilding its own payload.

The Planner runs up to `story_planner.PLANNER_STEPS_PER_REPLY` model calls
for one reply and the Dramaturge `dramaturge.DRAMATURGE_STEPS` for one pass,
and every step hands the model a payload whose derived half -- the story
row, the clock, the cast's minds, the thread, the mandates, the status row,
the frontier, the packages, the standing proposals -- comes out of the
database. `room_calls.ReplyMemo` holds that half until the reply writes
(review 2026-09-07, C21). This measures what it costs to build and what the
memo saves, and checks that the memoised payload is the same bytes as the
re-derived one.

NO MODEL CALLS. It builds payloads and never sends one, so it is safe
against a copy of a real story whose providers are blanked.

Run it against a COPY of a database, never a live one::

    ENGINE_DB=/tmp/copy.db .venv/bin/python tools/bench/room_payload.py \\
        /tmp/copy.db <chat-id> [--frame <frame-id>] [--steps N]

It prints, per agent: the cost of one payload, the cost of a whole reply
re-deriving every step, the cost with the memo held across the steps, and
whether the two agree byte for byte.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


def _median(values):
    values = sorted(values)
    return values[len(values) // 2]


def _encoded(payload):
    return json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)


def _run(label, build, steps, beat=None):
    """One payload's cost, then a whole reply's, memo off and memo on.

    ``beat`` is the live turn index the step loops hand the memo before
    every payload (`ReplyMemo.at_turn`), so the memoised figure carries the
    cost of noticing a beat that lands under the reply, exactly as the loops
    pay it."""
    from story.room_calls import ReplyMemo

    build(None)
    one = _median([_timed(build, None) for _ in range(5)])

    started = time.time()
    cold = [build(None) for _ in range(steps)]
    cold_seconds = time.time() - started

    memo = ReplyMemo()
    started = time.time()
    warm = []
    for _ in range(steps):
        if beat is not None:
            memo.at_turn(beat())
        warm.append(build(memo))
    warm_seconds = time.time() - started

    same = all(_encoded(a) == _encoded(b) for a, b in zip(cold, warm))
    print("%s: one payload %.1f ms | %d steps re-derived %.2f s, memoised "
          "%.2f s (%.0f%% off) | same bytes: %s"
          % (label, one * 1000, steps, cold_seconds, warm_seconds,
             100 * (1 - warm_seconds / cold_seconds) if cold_seconds else 0,
             same))


def _timed(build, memo):
    started = time.time()
    build(memo)
    return time.time() - started


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("db", help="path to a COPY of a database")
    ap.add_argument("chat_id", type=int)
    ap.add_argument("--frame", type=int, default=None)
    ap.add_argument("--steps", type=int, default=None,
                    help="model calls in the simulated reply "
                         "(default: each agent's own ceiling)")
    args = ap.parse_args()

    os.environ.setdefault("ENGINE_DB", args.db)
    from core import db
    db.configure(args.db)
    import agents.dramaturge as dramaturge
    import agents.story_planner as planner
    from story import room_conversation as room

    cid, frame_id = args.chat_id, args.frame
    turn_idx = room.current_turn_idx(cid)

    _run("planner",
         lambda memo: planner._payload(
             cid, frame_id, text="what stands ahead?", task=None,
             transcript=[], step=1, calls_left=5, seconds_left=100.0,
             turn_idx=turn_idx, memo=memo),
         args.steps or planner.PLANNER_STEPS_PER_REPLY,
         beat=lambda: room.current_turn_idx(cid))
    _run("dramaturge",
         lambda memo: dramaturge._payload(
             cid, frame_id, dial=2, brief=None, transcript=[], step=1,
             lore_left=4, seconds_left=100.0, turn_idx=turn_idx, memo=memo),
         args.steps or dramaturge.DRAMATURGE_STEPS,
         beat=lambda: room.current_turn_idx(cid))


if __name__ == "__main__":
    main()
