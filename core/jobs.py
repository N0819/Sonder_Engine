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
        # THE READ HORIZON (review R3-1, 2026-10-08): the newest beat this job
        # has read, raised by the job's own readers before they read
        # (`read_through`). It starts at the beat the job was queued from; a
        # job that loops reads later beats than that, and a restore decides by
        # what the job READ, not by when it was queued (`cancel_from`).
        self.read_turn = base_turn
        # Set by a restore that spared this job because it read only beats the
        # restore keeps: the newest beat it may still read. The beats after it
        # are being played again; the replayed beat's commit lifts it.
        self.read_limit = None
        # Set by a restore that stopped this job: the beat it took the story
        # back to, so the job can tell what it wrote from beats the restore
        # keeps from what it built on one it discards (`cancel_from`). None
        # for a job no restore stopped.
        self.cancelled_from = None
        self.state = "pending"        # pending|running|done|failed|cancelled
        self.result = None
        self.error = ""
        self.submitted = time.time()
        self.started = None
        self.finished = None
        self.cancelled = threading.Event()
        # A join's ask to run once more before the slot is released
        # (`submit_latest`), and the newest turn that asked: the next run's
        # `base_turn`. Read and cleared only under `_LOCK`.
        self.asked_again = False
        self.again_turn = None

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

    A CANCELLED JOB IS NEVER JOINED (review, 2026-10-08). Cancellation is
    cooperative, so a cancelled job holds its slot until the call it is
    inside returns -- for a Writers' Room pass, a Planner call of 10-21 s --
    and the submit that came in meanwhile joined work that had already been
    told to write nothing: a reroll's own commit, or a player's ask, queued
    nothing that ran. It starts fresh in the slot instead; the old job, when
    it finishes, no longer holds the slot, so it neither evicts the new one
    nor files a record (`_finish`).

    A JOB A RESTORE SPARED IS JOINED, AND HANDED THE NEWER BEAT (review
    R3-1): it read only beats the restore kept, and stops short of the beats
    being played again (`cancel_from`, `read_through`). A submit from a beat
    past its limit -- the replayed beat's own commit -- is the new timeline
    asking, so the limit lifts and the job reads on: one job per key still,
    and nothing it was asked for waits on a later commit.
    """
    with _LOCK:
        existing = _ACTIVE.get((chat_id, str(key)))
        if existing is not None and not existing.cancelled.is_set():
            if existing.read_limit is not None and base_turn is not None:
                try:
                    if int(base_turn) > int(existing.read_limit):
                        existing.read_limit = None
                except (TypeError, ValueError):
                    pass
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


def submit_latest(chat_id, key, fn, base_turn=None):
    """`submit`, for work that must answer the LATEST world rather than the
    one it read: a submit that finds the job already RUNNING asks it to run
    `fn` once more when this run returns, with `base_turn` the newest turn
    that asked, and returns it.

    `submit`'s join is right for work whose answer does not depend on when
    it started, and wrong for work that read the world once and works from
    what it read: a beat committed while it runs is joined to a run that
    will never see it. Measured on the rooms built in view (review of the
    2026-10-08 landing): a design run outlasts a sub-minute beat, so the
    next beat's commit joined it and a room that came into view on that beat
    waited for the first commit after the run ended -- about every other
    view, in fast play.

    ONE MORE RUN, NOT ONE PER ASK: the asks made during one run fold into
    the next, which reads the world as it then stands, so the work is
    bounded by the commits that asked and never stacks. A PENDING job has
    read nothing yet, so a join then asks nothing of it. The ask is made
    under the lock the job releases its slot under (`_run`), so it is either
    seen by the job or finds no job and starts one: no ask is lost between
    the job's last look and its finish, nor with a run that raises -- its
    failure is recorded and the asked run still goes. A cancelled job is
    never joined (`submit`)."""
    with _LOCK:
        existing = _ACTIVE.get((chat_id, str(key)))
        if (existing is not None and not existing.cancelled.is_set()
                and existing.state == "running"):
            existing.asked_again = True
            if base_turn is not None:
                try:
                    newer = (existing.again_turn is None
                             or int(base_turn) > int(existing.again_turn))
                except (TypeError, ValueError):
                    newer = True
                if newer:
                    existing.again_turn = base_turn
            return existing
    return submit(chat_id, key, fn, base_turn=base_turn)


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
    """Clear the turn-scoped vars from a job's inherited context.

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
        while True:
            try:
                result, failed = fn(job), False
            except Exception as exc:
                result, failed = None, True
                _record_failure(job, exc)
            with _LOCK:
                # ASKED AGAIN (`submit_latest`): one more run before the slot
                # is released, decided under the lock the ask is made under,
                # so an ask is either seen here or finds no job at all -- and
                # after a run that raised too, whose failure stays recorded:
                # the ask was lost with the failure (review of the 2026-10-08
                # rooms-in-view landing, round 3).
                if (job.asked_again and not job.cancelled.is_set()
                        and _ACTIVE.get((job.chat_id, job.key)) is job):
                    job.asked_again = False
                    if job.again_turn is not None:
                        job.base_turn, job.again_turn = job.again_turn, None
                    continue
                if failed:
                    return _finish_locked(job, "failed")
                job.result = result
                return _finish_locked(
                    job, "cancelled" if job.cancelled.is_set() else "done")
    except Exception as exc:
        _record_failure(job, exc)
        return _finish(job, "failed")


def _record_failure(job, exc):
    # Type and message, not a traceback: the point is to be countable
    # across turns, and above all to leave something saying this ran and
    # failed rather than never ran at all.
    job.error = "%s: %s" % (type(exc).__name__, str(exc)[:300])
    logger.info("job failed: chat=%s key=%s error=%s",
                job.chat_id, job.key, job.error)


def _finish(job, state):
    with _LOCK:
        return _finish_locked(job, state)


def _finish_locked(job, state):
    """`_finish` for a caller already holding `_LOCK` -- the run loop, which
    must decide "no ask came" and release the slot in one hold."""
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


def cancel_from(chat_id, key, turn_idx):
    """Ask the job under ``key`` to stop ONLY when it has READ a beat at or
    after ``turn_idx`` -- a beat a restore to ``turn_idx`` discards --
    returning it, or None when there is none or it read only beats the
    restore keeps. A job with no read horizon is asked to stop: the absence
    of a stamp is no evidence that it read nothing discarded.

    Restoring checkpoint N takes the story back to before beat N, so work
    that read only up to beat N-1 read nothing the restore throws away
    (review, 2026-10-08: rerolling beat 7 cancelled beat 6's deliberation,
    nothing re-armed it, and a proposal whose package had already published
    stayed open for the next deliberation to judge again).

    BY WHAT THE JOB READ, NOT WHEN IT WAS QUEUED (review R3-1, 2026-10-08).
    The Writers' Room's follow-up and its Dramaturge pass loop until nothing
    is left to do, and each round reads the beats played since: a job queued
    at beat 3 read beat 4, and a reroll of beat 4 left it writing what it
    built on the discarded beat. Its readers raise `Job.read_turn` before
    they read (`read_through`), and that is what is compared here.

    A JOB THIS SPARES may finish the unit of work it is in, but reads none
    of the beats the restore discards while they are being played again --
    their old narration stands until the replay replaces it: `read_through`
    stops it short of them, and it starts no new unit (`spared`) unless the
    replayed beat's own commit joins it (`submit` lifts the limit). The
    horizon check and the limit are one step under the lock, against
    `read_through` raising the horizon at the same moment."""
    with _LOCK:
        job = _ACTIVE.get((chat_id, str(key)))
        if job is None:
            return None
        horizon = job.read_turn
        if horizon is not None and turn_idx is not None:
            try:
                if int(horizon) < int(turn_idx):
                    limit = int(turn_idx) - 1
                    job.read_limit = limit if job.read_limit is None \
                        else min(int(job.read_limit), limit)
                    return None
            except (TypeError, ValueError):
                pass
        try:
            job.cancelled_from = None if turn_idx is None else int(turn_idx)
        except (TypeError, ValueError):
            job.cancelled_from = None
        job.cancelled.set()
    return job


def read_through(job, turn_idx):
    """A job's reader is about to read the story through beat ``turn_idx``:
    raise the job's read horizon (`Job.read_turn`) there FIRST, so a restore
    that comes after the read has begun sees it (`cancel_from`), and return
    the newest beat the reader may read -- ``turn_idx``, or less when a
    restore has spared the job and the later beats are being played again
    (`Job.read_limit`). The horizon never falls, and a job with none (no
    stamp: a restore always stops it) stays without one. ``job`` None -- a
    test, a panel reply, a caller outside any job -- reads ``turn_idx``."""
    if job is None or turn_idx is None or not hasattr(job, "read_turn"):
        return turn_idx
    with _LOCK:
        through = int(turn_idx)
        if job.read_limit is not None:
            through = min(through, int(job.read_limit))
        if job.read_turn is not None and through > int(job.read_turn):
            job.read_turn = through
    return through


def spared(job):
    """Whether a restore spared this job (`cancel_from`) and nothing has
    handed it a newer beat since (`submit`): it read only beats the restore
    kept, so it finishes the unit of work it is in -- and starts no other,
    because the next would read the beats being played again. False for
    None, like `is_cancelled`."""
    return getattr(job, "read_limit", None) is not None


def is_cancelled(job):
    """Whether the job a body was handed has been asked to stop. False for
    None, so work that also runs outside a job (a test, a panel reply) can
    ask unconditionally. A body that writes asks this before every write:
    cancellation is cooperative, so this is the only thing that stops a job
    whose model call was already under way when it was cancelled from
    writing what that call returned."""
    event = getattr(job, "cancelled", None)
    return bool(event is not None and event.is_set())


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
