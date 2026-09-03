"""Out-of-band work: jobs that run BETWEEN turns and never inside one.

Offscreen ticks, gap generation and anything else expensive must not sit
between the player and their prose. Two rules follow, and they are enforced
here rather than left to each caller to remember:

  * A job NEVER raises into the caller. `submit` returns a record; a failure
    is recorded ON it. Background work cannot fail a player's turn.
  * A job carries the turn it was scheduled FROM (`base_turn`), and
    `story_rewound_past` is how a consumer refuses a result whose era the
    story has left. What invalidates a result is a REWIND or a branch past
    `base_turn`, not the story taking further turns: a tick computed at turn
    40 is still true at turn 43, and refusing it there would discard every job
    that outlived one beat. base_turn does NOT catch the player walking into
    the place being ticked -- a consequence arriving before its cause is a
    separate hazard and is still open.

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

from core.logging_utils import logger

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
    try:
        # Copied so the story language reaches the job; `_run` immediately
        # drops the turn-scoped half of that copy. See
        # _clear_turn_scoped_context.
        context = contextvars.copy_context()
        threading.Thread(target=context.run, args=(_run, job, fn), daemon=True,
                         name="job-%s-%s" % (chat_id, job.key[:24])).start()
    except BaseException as exc:
        # The slot is published before the thread exists, so a failure to
        # START one stranded (chat_id, key) for the life of the process: there
        # is no supersede here, so every later submit for that key joined a
        # `pending` job with nothing behind it -- memory consolidation for that
        # chat silently never ran again. `Thread.start` raising RuntimeError
        # under thread exhaustion is the real trigger; BaseException, because a
        # bootstrap failure that is not an Exception strands the slot exactly
        # as completely, and this is the one place in the module where the
        # alternative to catching it is a queue that can never be used again.
        job.error = "%s: %s" % (type(exc).__name__, str(exc)[:300])
        logger.info("job could not start: chat=%s key=%s error=%s",
                    job.chat_id, job.key, job.error)
        _finish(job, "failed")
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
    """Clear the six turn-scoped vars from a job's inherited context.

    This is a DENYLIST, deliberately: the copy carries the story language and
    anything else a job legitimately needs across the thread hop, and
    `tests/test_jobs_queue.py`'s language test pins that inheritance. An
    allowlist would invert it and every producer would have to declare what its
    work reads.

    The cost of that choice is a standing obligation, stated here because it is
    invisible at the call site: a NEW contextvar in `llm/providers.py` or
    `core/pipeline_context.py` that belongs to one turn's wall clock must be
    added to this tuple, or it rides into background work by default. The
    question to ask of one is not "is it sensitive" but "does it name something
    that ends when the turn does" -- a sink writing into a persisted
    PipelineContext, an abort event, a step key. An audit of every contextvar
    in the tree (2026-08-19) found no other survivor that is live in
    background work: `db.active_frame_id` is the one that would matter and
    every job producer already sets it and resets in `finally`.
    """
    from core.pipeline_context import (current_decision_sink,
                                       current_exchange_sink,
                                       current_step_key,
                                       current_warning_sink)
    from llm.providers import (call_ledger_sink, cancel_event,
                           generation_event_sink, reasoning_sink, token_sink)

    # `reasoning_sink` rides here for the same reason `token_sink` does: the
    # Writers' Room arms it for one streamed reply, and a job started from
    # that reply's context would otherwise keep pushing a later model's
    # thinking at a queue whose reader has gone.
    for var in (token_sink, reasoning_sink, generation_event_sink,
                call_ledger_sink, cancel_event, current_warning_sink,
                current_step_key, current_decision_sink,
                current_exchange_sink):
        var.set(None)


def _run(job, fn):
    try:
        # Inside the try, not before it: the bootstrap imports `llm.providers`
        # and `core.pipeline_context`, and anything raised there used to escape
        # into a bare thread, leaving the job `pending` in `_ACTIVE` with no
        # worker -- the same stranded slot `submit` now guards against.
        _clear_turn_scoped_context()
        if job.cancelled.is_set():
            return _finish(job, "cancelled")
        with _LOCK:
            job.state = "running"
            job.started = time.time()
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
        # The same check gates the history write, which is what makes `reset`
        # safe against a worker still running: reset empties `_ACTIVE`, so a
        # job released afterwards no longer holds its slot and files nothing.
        # Without this a late finisher put its record into the history the
        # next test had just cleared.
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


def cancel_all():
    """Ask every active job in every chat to stop. Returns how many were asked.

    The process-wide half of `cancel_chat`, for a server shutting down: at that
    point there is no chat left to name.
    """
    with _LOCK:
        active = list(_ACTIVE.values())
    for job in active:
        job.cancelled.set()
    return len(active)


def drain(timeout=2.0):
    """Cancel everything and wait up to `timeout` seconds for it to file.

    Returns the jobs STILL in flight when the wait ran out -- empty when the
    queue drained, which is the ordinary case. Cooperative like `cancel`, so a
    job already inside a provider call finishes that call and a bounded
    shutdown can legitimately return a non-empty list; the threads are daemons
    and cannot hold the process open, so this reports rather than joins.
    """
    cancel_all()
    deadline = time.monotonic() + max(0.0, float(timeout))
    while True:
        with _LOCK:
            left = list(_ACTIVE.values())
        if not left or time.monotonic() >= deadline:
            return left
        time.sleep(0.01)


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


def story_rewound_past(base_turn, current_turn):
    """True when the story no longer stands at or after the turn a piece of
    out-of-band work was computed from -- it rewound underneath the job.

    This is the question every consumer of a `base_turn` asks, and it is the
    inverse of the one this helper asked until PERSISTENCE-F11. The story
    MOVING ON does not invalidate a result; the story going BACK does, because
    then the turn it was computed from is a future that has not happened.

    Takes turn numbers rather than a `Job`, because no consumer holds the job
    by the time its result lands: `base_turn` travels in the event payload,
    the artifact record or the landing call's own arguments.

    A missing number is never a refusal -- absence of a stamp is not evidence
    of anything, and the caller should know that, so it is said here rather
    than guessed at.
    """
    if base_turn is None or current_turn is None:
        return False
    return int(current_turn) < int(base_turn)


def reset():
    """Drop all queue state and ask everything still running to stop.

    It does not JOIN those threads -- cancellation is cooperative here, so work
    inside a provider call finishes that call -- but nothing they do afterwards
    reaches these tables: `_finish` writes only while the active table still
    holds THAT job, and this has just emptied it. Use `drain` when the caller
    can wait; this is for tests and for a fresh process, where waiting is the
    wrong trade.
    """
    with _LOCK:
        live = list(_ACTIVE.values())
        _ACTIVE.clear()
        _HISTORY.clear()
    for job in live:
        job.cancelled.set()
