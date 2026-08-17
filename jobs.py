"""Out-of-band work: jobs that run BETWEEN turns and never inside one.

Offscreen ticks, gap generation and anything else expensive must not sit
between the player and their prose. Two rules follow, and they are enforced
here rather than left to each caller to remember:

  * A job NEVER raises into the caller. `submit` returns a record; a failure
    is recorded ON it. Background work cannot fail a player's turn.
  * A job carries the turn it was scheduled FROM (`base_turn`). A result
    computed against turn N is not automatically valid at turn N+3, and
    `is_stale` is how a consumer refuses it. base_turn does NOT catch the
    player walking into the place being ticked -- a consequence arriving
    before its cause is a separate hazard and is still open.

This generalises the per-signature threading already in backdrops.py and
ambience.py, and closes two things reading them turned up: their per-signature
lock dicts are never pruned, and neither has any cancellation path. Here a
terminal job leaves the active table for a capped history, and cancellation is
explicit -- cooperative, so a job already inside a provider call finishes that
call and is then filed as cancelled rather than killed mid-flight.

Deliberately depends on nothing but the standard library and the engine
logger: no database, so scheduling is testable without ENGINE_DB.
"""

from __future__ import annotations

import contextvars
import threading
import time

from logging_utils import logger

# Terminal jobs are kept per chat so a failure is visible after the fact --
# out-of-band work that fails silently is worse than work that fails loudly.
# Capped, because unbounded growth is exactly the defect in the two queues
# this replaces.
_HISTORY_LIMIT = 32

_LOCK = threading.Lock()
_ACTIVE = {}      # (chat_id, key) -> Job, pending or running only
_HISTORY = {}     # chat_id -> [Job], oldest first, capped


class Job:
    """One unit of out-of-band work, and everything known about how it ended."""

    def __init__(self, chat_id, key, base_turn):
        self.chat_id = chat_id
        self.key = str(key)
        self.base_turn = base_turn
        self.state = "pending"        # pending|running|done|failed|cancelled
        self.result = None
        self.error = ""
        self.submitted = time.time()
        self.started = None
        self.finished = None
        self.cancelled = threading.Event()

    def as_dict(self):
        return {"chat_id": self.chat_id, "key": self.key,
                "base_turn": self.base_turn, "state": self.state,
                "error": self.error,
                "seconds": round(
                    (self.finished or time.time()) - self.submitted, 3)}


def submit(chat_id, key, fn, base_turn=None):
    """Queue `fn` and return its Job immediately. Never blocks, never raises.

    Deduped on (chat_id, key): a second submit while one is in flight joins
    the first rather than paying twice for the same work. `fn` is called as
    fn(job) so long work can consult `job.cancelled`.
    """
    with _LOCK:
        existing = _ACTIVE.get((chat_id, str(key)))
        if existing is not None:
            return existing
        job = Job(chat_id, key, base_turn)
        _ACTIVE[(chat_id, job.key)] = job
    # Copied so the story language reaches the job; `_run` immediately drops
    # the turn-scoped half of that copy. See _clear_turn_scoped_context.
    context = contextvars.copy_context()
    threading.Thread(target=context.run, args=(_run, job, fn), daemon=True,
                     name="job-%s-%s" % (chat_id, job.key[:24])).start()
    return job


#: Contextvars that belong to ONE turn's wall clock and must not ride into
#: background work, even though the copied context carries them.
#:
#: `submit` copies the whole context so the story language (and anything else
#: a job legitimately needs) survives the thread hop. That copy is taken inside
#: the commit step, whose context holds the live stream's `token_sink`, the
#: turn's abort `cancel_event`, and sinks writing into a `PipelineContext`
#: whose variants are already persisted. Left in place, a background
#: consolidation streams tokens into the player's finished turn tagged
#: `key="commit"`, and an abort kills the jobs that commit just scheduled.
#: `offscreen.py`'s `_produce` argued exactly this before the copy existed.
def _clear_turn_scoped_context():
    from pipeline_context import current_step_key, current_warning_sink
    from providers import (call_ledger_sink, cancel_event,
                           generation_event_sink, token_sink)

    for var in (token_sink, generation_event_sink, call_ledger_sink,
                cancel_event, current_warning_sink, current_step_key):
        var.set(None)


def _run(job, fn):
    _clear_turn_scoped_context()
    if job.cancelled.is_set():
        return _finish(job, "cancelled")
    with _LOCK:
        job.state = "running"
        job.started = time.time()
    try:
        result = fn(job)
    except Exception as exc:
        # Type and message, not a traceback: the point is to be countable
        # across turns, and above all to leave something saying this ran and
        # failed rather than never ran at all.
        job.error = "%s: %s" % (type(exc).__name__, str(exc)[:300])
        logger.info("job failed: chat=%s key=%s error=%s",
                    job.chat_id, job.key, job.error)
        return _finish(job, "failed")
    job.result = result
    return _finish(job, "cancelled" if job.cancelled.is_set() else "done")


def _finish(job, state):
    with _LOCK:
        job.state = state
        job.finished = time.time()
        # Identity check, not a bare delete: a later job under the same key
        # must not be evicted by an older one finishing late.
        if _ACTIVE.get((job.chat_id, job.key)) is job:
            del _ACTIVE[(job.chat_id, job.key)]
        past = _HISTORY.setdefault(job.chat_id, [])
        past.append(job)
        del past[:-_HISTORY_LIMIT]
    return job


def cancel(chat_id, key):
    """Ask one job to stop, returning it or None.

    Cooperative: work already inside a provider call runs to the end of that
    call and is then filed as cancelled. This bounds what is USED, not what is
    spent.
    """
    with _LOCK:
        job = _ACTIVE.get((chat_id, str(key)))
    if job is None:
        return None
    job.cancelled.set()
    return job


def cancel_chat(chat_id):
    """Cancel every active job for a chat. Returns how many were asked."""
    with _LOCK:
        active = [j for (cid, _k), j in _ACTIVE.items() if cid == chat_id]
    for job in active:
        job.cancelled.set()
    return len(active)


def status(chat_id, key):
    """'pending' | 'running' | 'done' | 'failed' | 'cancelled' | 'absent'."""
    with _LOCK:
        job = _ACTIVE.get((chat_id, str(key)))
        if job is not None:
            return job.state
        for past in reversed(_HISTORY.get(chat_id, [])):
            if past.key == str(key):
                return past.state
    return "absent"


def history(chat_id):
    with _LOCK:
        return list(_HISTORY.get(chat_id, []))


def active_jobs(chat_id=None):
    with _LOCK:
        return [j for (cid, _k), j in _ACTIVE.items()
                if chat_id is None or cid == chat_id]


def is_stale(job, current_turn):
    """True when the story has moved past the turn this job was computed from.

    A job with no base_turn is never stale by this test -- absence of a stamp
    is not evidence of freshness, and the caller should know that, so it is
    said here rather than guessed at.
    """
    if job is None or job.base_turn is None or current_turn is None:
        return False
    return int(current_turn) > int(job.base_turn)


def reset():
    """Drop all queue state. For tests and for a fresh process; it does not
    stop threads already running."""
    with _LOCK:
        _ACTIVE.clear()
        _HISTORY.clear()
