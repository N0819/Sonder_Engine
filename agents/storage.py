"""Step and variant persistence helpers."""

from __future__ import annotations

import json
import time

from db import q, qi, transaction

def save_step(turn_id, key, label, ordn, content):
    # Deactivating the old variant and activating the new one used to be
    # two separate autocommitted statements -- a crash between them could
    # leave a step with zero active variants, silently breaking the "one
    # active variant per step" invariant everything else (resume, pipeline
    # display) relies on. Wrapped in one transaction so it's all-or-nothing.
    with transaction():
        s = q("SELECT * FROM steps WHERE turn_id=? AND key=?", (turn_id, key), one=True)
        if s:
            sid = s["id"]
            qi("UPDATE steps SET label=?,ord=?,stale=0 WHERE id=?", (label, ordn, sid))
        else:
            sid = qi("INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
                      (turn_id, key, label, ordn))
        qi("UPDATE variants SET active=0 WHERE step_id=?", (sid,))
        vid = qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                 (sid, json.dumps(content), time.time()))
        n = q("SELECT COUNT(*) c FROM variants WHERE step_id=?", (sid,), one=True)["c"]
    return sid, vid, n

def active_content(turn_id, key):
    r = q("SELECT v.content FROM steps s JOIN variants v "
          "ON v.step_id=s.id AND v.active=1 "
          "WHERE s.turn_id=? AND s.key=?", (turn_id, key), one=True)
    return json.loads(r["content"]) if r else None

def variant_count(turn_id, key):
    r = q("SELECT COUNT(v.id) c FROM steps s JOIN variants v "
          "ON v.step_id=s.id WHERE s.turn_id=? AND s.key=?", (turn_id, key), one=True)
    return r["c"] if r else 0

def step_is_stale(turn_id, key):
    r = q("SELECT stale FROM steps WHERE turn_id=? AND key=?", (turn_id, key), one=True)
    return bool(r and r["stale"])

def _set_steps_stale(turn_id, keys, stale: bool):
    keys = list(keys)
    if not keys:
        return
    placeholders = ",".join("?" for _ in keys)
    qi(f"UPDATE steps SET stale=? WHERE turn_id=? AND key IN ({placeholders})",
       (1 if stale else 0, turn_id, *keys))

def mark_steps_stale(turn_id, keys):
    """Mark the given step keys stale for a turn, if they already exist.

    Called BEFORE (re)computing a run's steps, not after -- so that if
    the run is interrupted partway through, the steps not yet reached
    are visibly stale rather than silently retaining stale=0 from a
    previous, now-inconsistent run. Without this, resume_key_for_turn
    can look at an untouched downstream step from an earlier run and
    conclude the turn is already complete, even though its content no
    longer matches the just-recomputed upstream steps it depended on.
    """
    _set_steps_stale(turn_id, keys, True)

def clear_steps_stale(turn_id, keys):
    """Clear stale on exactly the given (plan) keys once a run finishes
    successfully -- deliberately scoped rather than clearing every step
    row for the turn, so orphaned steps left behind by a replan (see
    save_step's caller in runtime.py) keep showing as stale/orphaned
    instead of being marked falsely fresh."""
    _set_steps_stale(turn_id, keys, False)
