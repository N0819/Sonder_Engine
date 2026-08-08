"""The bounded machinery both out-of-band queues run on.

`backdrops.py` (images) and `ambience.py` (room audio) are twins by
construction -- same three rules, same per-signature threading, and ambience's
own docstring says it is "deliberately built as the audio twin of
backdrops.py". So they leaked in the same two ways, which is what a copied
pattern does:

  * **Four tables that grew with the key space, not with the work.** Each kept
    a lock per signature and pruned none of them, so a long chat accumulated a
    dead entry per distinct room-state for the life of the process. Each also
    kept a per-signature error string, and the only thing that ever removed one
    was somebody asking for that exact signature again -- which a reader who
    never walks back into that room never does. Measured on the unmodified
    modules: 500 distinct signatures left 500 locks and 500 remembered errors
    standing, in both modules, ~62KB of tables for zero live work.

  * **No cancellation path at all.** Once submitted, work ran to completion
    even when nothing wanted the result any more.

Both are properties of the PATTERN, so the pattern lives here once instead of
being fixed twice and drifting a third time.

Two things this is deliberately not:

  * **Not a replacement for `jobs.py`** (branch `agent-engine`), which solves
    the same two problems for offscreen ticks and gap generation. It is not
    merged, so importing it is not available; copying it here would fork the
    one module whose entire purpose is to stop this pattern being forked, and
    the merge would then be a three-way conflict on a concurrency primitive.
    This is the same shape deliberately -- terminal work leaves the active
    table, cancellation is cooperative and BETWEEN steps -- so that when
    `jobs.py` lands, this module is the single seam to delete rather than two
    hand-written queues to reconcile.

  * **Not a thread pool.** Each unit of work gets a thread, exactly as before.
    These are two or three concurrent network calls, not a workload, and
    bounding concurrency is a different question from bounding memory.

Standard library and the engine logger only -- no database, so scheduling is
testable without ENGINE_DB.
"""

from __future__ import annotations

import contextlib
import threading

from logging_utils import logger

# How many past failures one queue remembers. Capped for the same reason the
# lock table is pruned, and small on purpose: a remembered error exists so the
# picture that never appeared can explain itself to the reader looking at that
# room now, not to an audit of the whole session. `jobs.py` caps its history at
# the same 32.
ERROR_LIMIT = 32


class KeyedLocks:
    """One mutex per key, and no entry for a key nobody is on.

    The dict this replaces was never pruned, and the comment saying why --
    "pruning it would race with the waiters" -- was true of a bare `del`: a
    thread blocked on a lock leaves no evidence anywhere that it wants that
    lock, so the holder about to leave cannot tell whether anyone is behind it.

    A waiter counts itself in BEFORE it lets go of the guard, so the count IS
    that evidence and the race is gone. An entry is dropped only at zero, and
    only by the thread that took it there.
    """

    def __init__(self):
        self._guard = threading.Lock()
        self._locks = {}          # key -> [lock, waiters]

    def __len__(self):
        """How many keys are currently held or waited on. Zero when idle --
        which is the whole point, and what the regression test asserts."""
        with self._guard:
            return len(self._locks)

    @contextlib.contextmanager
    def hold(self, key):
        with self._guard:
            entry = self._locks.get(key)
            if entry is None:
                entry = self._locks[key] = [threading.Lock(), 0]
            # Under the guard, before acquiring: from here the entry cannot be
            # deleted out from under us, so the lock object every holder and
            # waiter of this key acquires is guaranteed to be the same one.
            entry[1] += 1
            lock = entry[0]
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self._guard:
                entry = self._locks.get(key)
                if entry is not None:
                    entry[1] -= 1
                    if entry[1] <= 0:
                        del self._locks[key]


class Work:
    """One unit of out-of-band work, and how it ended."""

    def __init__(self, signature, group=None):
        self.signature = str(signature)
        # The chat, so a whole story's pending work can be stopped at once.
        # Deliberately NOT part of the dedup key: a branch inherits its
        # parent's signatures and must JOIN the generation already running for
        # one rather than pay for the identical picture again.
        self.group = group
        self.state = "pending"        # pending|running|done|failed|cancelled
        self.error = ""
        self.cancelled = threading.Event()


def stopped(work):
    """True when this unit of work has been asked to stop.

    Takes the Work rather than its Event so that every direct, blocking caller
    of a generator -- which has nothing to cancel and passes None -- reads
    correctly instead of having to remember a guard.
    """
    return work is not None and work.cancelled.is_set()


class Queue:
    """Signature-keyed background work that never blocks the caller."""

    def __init__(self, name, error_limit=ERROR_LIMIT):
        self._name = name
        self._error_limit = error_limit
        self._guard = threading.Lock()
        self._active = {}     # signature -> Work, pending or running only
        self._errors = {}     # signature -> str, insertion-ordered and capped

    def __len__(self):
        with self._guard:
            return len(self._active)

    def submit(self, signature, fn, group=None, supersede=False):
        """Start `fn(work)` on a thread. Returns the Work, or None when one was
        already in flight for this signature and this caller simply joined it.

        Never blocks and never raises into the caller: a failure is recorded on
        the queue, because a route asking for a backdrop must get "pending"
        straight back whatever happens next.
        """
        signature = str(signature)
        with self._guard:
            existing = self._active.get(signature)
            if existing is not None and not supersede:
                return None
            work = Work(signature, group)
            self._active[signature] = work
            # A fresh attempt clears the last failure, so a retry is not
            # reported as still broken while it is running.
            self._errors.pop(signature, None)
        if existing is not None:
            # Superseded, not joined. `force` and `reroll` are explicit
            # instructions, and the answer the incumbent is about to produce is
            # precisely the one they were issued to replace -- so joining it
            # silently dropped the instruction. The incumbent stops at its next
            # step boundary; the per-signature lock keeps the two off each
            # other in the meantime.
            existing.cancelled.set()
        threading.Thread(target=self._run, args=(work, fn), daemon=True,
                         name="%s-%s" % (self._name, signature[:8])).start()
        return work

    def _run(self, work, fn):
        if work.cancelled.is_set():
            return self._finish(work, "cancelled")
        work.state = "running"
        try:
            fn(work)
        except Exception as exc:
            # Type and message, not a traceback: this is a routine
            # provider-shaped failure, and the point is to be countable across
            # turns and above all to leave something saying this RAN AND FAILED
            # rather than never ran at all.
            return self._fail(work, "%s: %s" % (type(exc).__name__,
                                                str(exc)[:300]))
        return self._finish(work,
                            "cancelled" if work.cancelled.is_set() else "done")

    def _fail(self, work, message):
        with self._guard:
            work.state = "failed"
            work.error = message
            self._retire(work)
            self._errors[work.signature] = message
            # Oldest out first: the failures a reader is still looking at are
            # the recent ones, and the alternative -- keeping all of them -- is
            # the leak this module exists to close.
            while len(self._errors) > self._error_limit:
                self._errors.pop(next(iter(self._errors)))
        logger.info("%s work failed: signature=%s error=%s",
                    self._name, work.signature, message)
        return work

    def _finish(self, work, state):
        with self._guard:
            work.state = state
            self._retire(work)
        return work

    def _retire(self, work):
        # Identity check, not a bare delete: work that SUPERSEDED this one must
        # not be evicted from the table by the one it replaced finishing late.
        if self._active.get(work.signature) is work:
            del self._active[work.signature]

    def status(self, signature):
        """'pending' | 'error' | 'absent' for one signature.

        Cancelled work reports 'absent': nothing was produced and asking again
        is allowed. Deliberately not folded in with 'error' -- the error table
        exists so that a FAILURE is visible rather than silent, and a stop
        somebody asked for is not a failure.
        """
        signature = str(signature)
        with self._guard:
            if signature in self._active:
                return "pending"
            if signature in self._errors:
                return "error"
        return "absent"

    def error(self, signature):
        """The last recorded failure for this signature, or None.

        Kept because the alternative is out-of-band work that never appears and
        never explains itself, which is worse than work that fails loudly.
        """
        with self._guard:
            return self._errors.get(str(signature))

    def cancel(self, signature):
        """Ask one unit of work to stop, returning it or None."""
        with self._guard:
            work = self._active.get(str(signature))
        if work is None:
            return None
        work.cancelled.set()
        return work

    def cancel_group(self, group):
        """Ask everything in flight for one chat to stop. Returns how many.

        Cooperative: work already inside a provider call runs to the end of
        that call and is then filed as cancelled rather than killed mid-flight.
        This bounds what is USED, not what is spent -- a half-written image is
        worse than a wasted one.
        """
        with self._guard:
            works = [w for w in self._active.values() if w.group == group]
        for work in works:
            work.cancelled.set()
        return len(works)

    def active(self, group=None):
        with self._guard:
            return [w for w in self._active.values()
                    if group is None or w.group == group]

    def reset(self):
        """Drop all queue state. For tests and for a fresh process; it does not
        stop threads already running."""
        with self._guard:
            self._active.clear()
            self._errors.clear()
