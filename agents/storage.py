"""Step and variant persistence helpers."""

from __future__ import annotations

import json
import time

from db import q, qi, transaction

# Reserved key on a step's saved content carrying what the DETERMINISTIC layer
# did to that step's output: repairs it made, and which steps it ran beside.
# Written by `agents.runtime._with_engine_notes`, read by the pipeline UI.
#
# It lives in the content rather than in a column on purpose. It is
# per-variant by nature (a reroll repairs differently), it rides every
# archive, branch, checkpoint and trace for free because those all carry step
# content as opaque JSON, and it needs no migration.
ENGINE_NOTES_KEY = "_engine_notes"


def save_step(turn_id, key, label, ordn, content, reasoning=None):
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
        # The reasoning trace belongs to the call that just produced this
        # content. It is PASSED IN when the caller ran that call on another
        # thread, because `last_reasoning` is a ContextVar and a value set in
        # a worker is not visible here -- which is every pipeline step, and is
        # why this stored nothing at all for as long as the column existed.
        # The ContextVar read stays as the fallback for a caller on the same
        # thread as its own model call. Diagnostic only -- never read back as
        # content.
        if reasoning:
            _think = str(reasoning)[:20000]
        else:
            try:
                from providers import last_reasoning
                _think = str(last_reasoning.get() or "")[:20000]
            except Exception:
                _think = ""
        vid = qi("INSERT INTO variants(step_id,content,created,active,reasoning) "
                 "VALUES(?,?,?,1,?)",
                 (sid, json.dumps(content), time.time(), _think))
        n = q("SELECT COUNT(*) c FROM variants WHERE step_id=?", (sid,), one=True)["c"]
    return sid, vid, n

def active_content(turn_id, key):
    r = q("SELECT v.content FROM steps s JOIN variants v "
          "ON v.step_id=s.id AND v.active=1 "
          "WHERE s.turn_id=? AND s.key=?", (turn_id, key), one=True)
    if not r:
        return None
    content = json.loads(r["content"])
    # The engine notes are ABOUT this content, not part of it. This is the
    # read path a rerun rehydrates through -- ctx[key] = active_content(...) --
    # and several stages hand a prior step's dict to a model wholesale, so
    # leaving them in would put the engine's own repair log into a prompt on
    # every rerun and nowhere else, which is the worst kind of difference
    # between a fresh run and a resumed one. The pipeline UI reads the
    # variants table directly and still sees them.
    if isinstance(content, dict) and ENGINE_NOTES_KEY in content:
        content = {k: v for k, v in content.items() if k != ENGINE_NOTES_KEY}
    return content

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

def delete_step(step_id):
    """Delete a step and all its variants atomically.

    A crash between deleting variants and deleting the step row would
    leave a step with zero variants, breaking the "one active variant
    per step" invariant. Wrapped in one transaction so it's all-or-nothing.
    """
    with transaction():
        qi("DELETE FROM variants WHERE step_id=?", (step_id,))
        qi("DELETE FROM steps WHERE id=?", (step_id,))
