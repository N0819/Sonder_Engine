#!/usr/bin/env python3
"""Replay the one beat where a character asked the world for something.

THE CHECKPOINT, and why this beat. Aldermill's fourth run, turn idx 15,
frame 2: Sal Weatherby -- whose drive is "know how a place really works,
asks the people nobody asks" -- leaned off a bench, raised two fingers at
the inn's floor staff and said

    "Small ale, when you've a moment."

It is the first thing either character had asked of anybody in 220 beats
across four runs, and nothing happened. `intended_target` came back null, so
the voice gate had no name to route to, `background_react` never fired, and
four staff stood in the room while the order hung in the air.

WHAT THIS MEASURES, in order of how much it would mean:

  1. did anyone ANSWER her (a line back);
  2. did anyone ACT on it (`background_react.action`, `charter_act`, a body
     crossing to the tap);
  3. did she END UP WITH AN ALE -- a thing, in her hands, that the scene
     holds after the beat.

(3) is the whole question. A world that can be read but cannot be ASKED is
half a world, and a world that answers but cannot serve is three quarters of
one. Speech is cheap; the ale is the test.

    python3 tools/ale_checkpoint.py            # replay once, report
    python3 tools/ale_checkpoint.py --keep     # leave the scratch db behind
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SOURCE = os.path.expanduser("~/.cache/sonder_runs/ale_checkpoint.db")
SCRATCH = os.path.expanduser("~/.cache/sonder_runs/ale_replay.db")
CHAT, FRAME, IDX = 1, 2, 15
ASKER = "Sal Weatherby"


def _fresh_copy():
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(SCRATCH + suffix):
            os.remove(SCRATCH + suffix)
    shutil.copy(SOURCE, SCRATCH)
    return SCRATCH


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(SOURCE):
        raise SystemExit("no checkpoint db at %s" % SOURCE)
    os.environ["ENGINE_DB"] = _fresh_copy()

    from core import db
    from core.db import active_frame_id, wget_for_frame
    from persist.checkpoints import restore_checkpoint

    restore_checkpoint(CHAT, IDX)

    before = wget_for_frame(CHAT, "scene", FRAME, {}) or {}
    held_before = json.dumps((before.get("entities") or {}))

    from agents.offscreen_beat import run_offscreen_beat
    out = run_offscreen_beat(CHAT, FRAME)
    turn_id = out["turn_id"]

    def step(key):
        row = db.q("SELECT v.content FROM steps s JOIN variants v "
                   "ON v.step_id=s.id AND v.active=1 "
                   "WHERE s.turn_id=? AND s.key=?", (turn_id, key), one=True)
        return json.loads(row["content"]) if row else {}

    resolve, background = step("director_resolve"), step("background_react")
    after = wget_for_frame(CHAT, "scene", FRAME, {}) or {}

    lines = resolve.get("dialogue_log") or []
    answered = [d for d in lines
                if str(d.get("speaker") or "") != ASKER]
    diff = resolve.get("state_diff") or {}

    print("\n--- the ale checkpoint (idx %d, frame %d) ---" % (IDX, FRAME))
    print("1. ANSWERED   %s" % ("yes: " + json.dumps(
        [d.get("exact_quote") for d in answered])[:180] if answered else "no"))
    print("   (she said: %s)" % json.dumps(
        [d.get("exact_quote") for d in lines
         if str(d.get("speaker") or "") == ASKER])[:150])
    print("2. ACTED      fired=%s name=%s action=%r charter_act=%r goes_to=%r"
          % (background.get("fired"), background.get("name"),
             str(background.get("action") or "")[:70],
             str(background.get("charter_act") or "")[:40],
             str(background.get("goes_to") or "")[:30]))
    print("3. THE ALE    inventory_ops=%s" % json.dumps(diff.get("inventory_ops"))[:200])
    print("   entities changed: %s" % (
        "yes" if json.dumps(after.get("entities") or {}) != held_before else "no"))
    print("   contacts: %s" % json.dumps(diff.get("contact_ops"))[:180])
    print("\n   channels this beat: %s"
          % ", ".join(sorted(k for k, v in diff.items() if v)))
    print("   seconds: %s" % out.get("seconds"))
    if not args.keep:
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(SCRATCH + suffix):
                os.remove(SCRATCH + suffix)
    return out


if __name__ == "__main__":
    main()
