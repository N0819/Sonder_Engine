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

  * **Not a replacement for `core/jobs.py`**, which solves the same two
    problems for offscreen ticks, artifact generation and memory
    consolidation. It has LANDED -- `world/offscreen.py`, `story/artifacts.py`,
    `persist/checkpoints.py` and `persist/commit_memory_write.py` all import
    it -- so "it is not merged, importing it is not available", which this
    paragraph used to say, is no longer why the two are separate. Nothing
    replaced this module when jobs.py arrived, and the two are still the same
    shape on purpose: terminal work leaves the active table, cancellation is
    cooperative and BETWEEN steps. Collapsing them is therefore one merge with
    a single seam to delete, and it is UNFINISHED rather than unavailable --
    which is a different question from the one this comment was answering, and
    the one a reader should be left with.

  * **Not a thread pool.** Each unit of work gets a thread, exactly as before.
    These are two or three concurrent network calls, not a workload, and
    bounding concurrency is a different question from bounding memory.

Standard library and the engine logger only -- no database, so scheduling is
testable without ENGINE_DB.
"""

from __future__ import annotations

import contextlib
import threading
import time
import weakref

from core.logging_utils import logger

# Every live queue, so a process shutting down can reach all of them through
# `drain_all` without importing `backdrops` and `ambience` to name the two they
# own. Weak, because a queue built for one test must not be kept alive -- or
# drained -- by this registry after that test drops it.
_QUEUES = weakref.WeakSet()

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
        _QUEUES.add(self)

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
        try:
            threading.Thread(target=self._run, args=(work, fn), daemon=True,
                             name="%s-%s" % (self._name,
                                             signature[:8])).start()
        except BaseException as exc:
            # The replacement is already published and cannot make progress, so
            # leaving it there wedges the signature: `submit` joins the
            # incumbent on the ordinary path, so every later request for that
            # room's picture or sound would join a worker that does not exist
            # and poll to its 75s budget, and only another forced reroll could
            # clear it. `_fail` records the failure and releases the slot by
            # the same identity check every other exit uses, and hands the
            # signature back to the incumbent under the same guard.
            return self._fail(work, "%s: %s" % (type(exc).__name__,
                                                str(exc)[:300]),
                              restore=existing)
        if existing is not None:
            # Superseded, not joined. `force` and `reroll` are explicit
            # instructions, and the answer the incumbent is about to produce is
            # precisely the one they were issued to replace -- so joining it
            # silently dropped the instruction. The incumbent stops at its next
            # step boundary; the per-signature lock keeps the two off each
            # other in the meantime.
            #
            # AFTER the start, never before: invalidating the one that works on
            # behalf of a replacement that then failed to start left the room
            # with no generation running at all.
            existing.cancelled.set()
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

    def _fail(self, work, message, restore=None):
        with self._guard:
            # Identity, for the error table as much as for the active one.
            # `_retire` was checked and this write was not, so a unit that had
            # been SUPERSEDED and then failed filed its message over the reroll
            # that replaced it -- and if the reroll succeeded, the signature
            # reported 'error' with the message of an attempt nobody was
            # waiting on, undoing the guarantee `submit` gives two lines above.
            # It also makes `reset` safe against a worker still running: reset
            # empties the active table, so a late failure writes nothing.
            mine = self._active.get(work.signature) is work
            work.state = "failed"
            work.error = message
            self._retire(work)
            if restore is not None:
                # A replacement that could not start hands the signature back
                # to the unit it was going to supersede, inside the same guard
                # so no reader finds the slot empty in between. setdefault, not
                # assignment: anything that claimed the signature meanwhile is
                # live and this is not.
                self._active.setdefault(work.signature, restore)
            if mine:
                self._errors[work.signature] = message
                # Oldest out first: the failures a reader is still looking at
                # are the recent ones, and the alternative -- keeping all of
                # them -- is the leak this module exists to close.
                while len(self._errors) > self._error_limit:
                    self._errors.pop(next(iter(self._errors)))
        logger.info("%s work failed: signature=%s error=%s",
                    self._name, work.signature, message)
        return work

    def _finish(self, work, state):
        with self._guard:
            work.state = state
            mine = self._active.get(work.signature) is work
            self._retire(work)
            if mine and state == "done":
                # `submit` clears the last failure when a fresh attempt STARTS;
                # nothing cleared it when one SUCCEEDED, so a message written
                # by a sibling while this attempt was already running outlived
                # the picture it was supposed to explain the absence of.
                self._errors.pop(work.signature, None)
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

    def cancel_all(self):
        """Ask everything in flight to stop, whatever group it belongs to.

        The process-wide half of `cancel_group`, for a server shutting down: at
        that point there is no chat left to name.
        """
        with self._guard:
            works = list(self._active.values())
        for work in works:
            work.cancelled.set()
        return len(works)

    def drain(self, timeout=2.0):
        """Cancel everything and wait up to `timeout` seconds for it to file.

        Returns what is STILL in flight when the wait runs out -- empty when
        the queue drained. Cooperative like `cancel`, so work inside a provider
        call finishes that call and a bounded shutdown can legitimately return
        a non-empty list; the threads are daemons and cannot hold the process
        open, so this reports rather than joins.
        """
        self.cancel_all()
        return self._wait_out(time.monotonic() + max(0.0, float(timeout)))

    def _wait_out(self, deadline):
        while True:
            with self._guard:
                left = list(self._active.values())
            if not left or time.monotonic() >= deadline:
                return left
            time.sleep(0.01)

    def active(self, group=None):
        with self._guard:
            return [w for w in self._active.values()
                    if group is None or w.group == group]

    def reset(self):
        """Drop all queue state and ask everything still running to stop.

        It does not JOIN those threads -- cancellation is cooperative here --
        but nothing they do afterwards reaches this queue: `_fail` and
        `_finish` both write only while the active table still holds THAT unit,
        and this has just emptied it. Without that, a worker released after the
        tables were cleared repopulated `_errors` for whoever came next. Use
        `drain` when the caller can wait; this is for tests and for a fresh
        process, where waiting is the wrong trade.
        """
        with self._guard:
            live = list(self._active.values())
            self._active.clear()
            self._errors.clear()
        for work in live:
            work.cancelled.set()


def drain_all(timeout=2.0):
    """Cancel and drain every live queue, inside one shared `timeout`.

    One entry point for a process shutting down, so the caller does not have to
    import `backdrops` and `ambience` to reach the two queues they own.
    Everything is cancelled first and waited on afterwards, so the budget is
    spent once rather than per queue. Returns what is still in flight when it
    runs out.
    """
    queues = list(_QUEUES)
    for queue in queues:
        queue.cancel_all()
    deadline = time.monotonic() + max(0.0, float(timeout))
    left = []
    for queue in queues:
        left.extend(queue._wait_out(deadline))
    return left
