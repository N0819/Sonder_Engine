"""The queue offscreen work runs on.

What it must guarantee is that a turn is never blocked by background work,
never failed by it, and never handed a result computed against a world that
has since moved. No database: scheduling is not a storage question, and these
run without ENGINE_DB.
"""

import threading
import time
import contextvars

import pytest

from core import jobs


@pytest.fixture(autouse=True)
def _clean_queue():
    jobs.reset()
    yield
    jobs.reset()


def _wait(pred, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.005)
    return False


def test_submit_returns_without_waiting_for_the_work():
    # The whole reason this module exists: the caller is a turn.
    release = threading.Event()
    started = threading.Event()

    def slow(job):
        started.set()
        release.wait(3.0)
        return "done"

    t0 = time.time()
    job = jobs.submit(1, "tick", slow, base_turn=4)
    assert time.time() - t0 < 0.5
    assert _wait(started.is_set)
    release.set()
    assert _wait(lambda: job.state == "done")
    assert job.result == "done"


def test_the_same_key_twice_is_one_piece_of_work():
    release = threading.Event()
    calls = []

    def slow(job):
        calls.append(job)
        release.wait(3.0)

    first = jobs.submit(1, "tick", slow, base_turn=4)
    assert _wait(lambda: first.state == "running")
    second = jobs.submit(1, "tick", slow, base_turn=4)
    assert second is first
    release.set()
    assert _wait(lambda: first.state == "done")
    assert len(calls) == 1


def test_a_job_that_raises_leaves_a_record_and_never_reaches_the_caller():
    # A background failure that vanishes is indistinguishable afterwards from
    # work that never ran -- which is the state the existing queues are in.
    def boom(job):
        raise ValueError("provider said no")

    job = jobs.submit(2, "gap", boom, base_turn=1)
    assert _wait(lambda: job.state == "failed")
    assert job.error == "ValueError: provider said no"
    assert jobs.status(2, "gap") == "failed"
    assert job in jobs.history(2)


def test_the_story_moving_on_does_not_invalidate_a_result():
    """PERSISTENCE-F11. `is_stale` refused a result the moment the story took
    one more turn, which is not what any consumer of `base_turn` wanted: an
    offscreen tick computed at turn 7 is still true at turn 8, and refusing it
    there would discard every job that outlived a single beat."""
    assert jobs.story_rewound_past(7, 7) is False
    assert jobs.story_rewound_past(7, 8) is False
    assert jobs.story_rewound_past(7, 900) is False


def test_a_story_rewound_underneath_a_job_refuses_its_result():
    """The rule the four real consumers each hand-rolled: the turn the work was
    computed from is a future that has not happened."""
    assert jobs.story_rewound_past(7, 6) is True
    assert jobs.story_rewound_past(7, 0) is True


def test_an_unstamped_job_is_not_reported_rewound():
    job = jobs.submit(3, "unstamped", lambda job: "ok")
    assert _wait(lambda: job.state == "done")
    assert job.base_turn is None
    assert jobs.story_rewound_past(job.base_turn, 99) is False
    assert jobs.story_rewound_past(7, None) is False


def test_cancelling_files_the_job_as_cancelled_rather_than_done():
    def cooperative(job):
        job.cancelled.wait(3.0)
        return "partial"

    job = jobs.submit(4, "tick", cooperative, base_turn=2)
    assert _wait(lambda: job.state == "running")
    assert jobs.cancel_chat(4) == 1
    assert _wait(lambda: job.state == "cancelled")
    assert jobs.status(4, "tick") == "cancelled"


def test_a_submit_never_joins_a_cancelled_job():
    """(review F, 2026-10-08) Cancellation is cooperative, so a cancelled job
    holds its slot until the call it is inside returns -- for a Writers' Room
    pass, a Planner call of 10-21 s -- and a submit meanwhile joined work
    already told to write nothing: a reroll's own commit queued nothing that
    ran. It starts fresh, and the old job, finishing late, neither evicts
    the new one nor files a record."""
    release = threading.Event()

    def stubborn(_job):
        release.wait(3.0)
        return "old"

    old = jobs.submit(14, "tick", stubborn, base_turn=4)
    assert _wait(lambda: old.state == "running")
    assert jobs.cancel(14, "tick") is old
    ran = threading.Event()
    new = jobs.submit(14, "tick", lambda _job: ran.set() or "new", base_turn=4)
    assert new is not old
    assert _wait(ran.is_set)
    assert _wait(lambda: new.state == "done")
    release.set()
    assert _wait(lambda: old.state == "cancelled")
    assert jobs.status(14, "tick") == "done"
    assert old not in jobs.history(14) and new in jobs.history(14)


def test_a_restore_cancels_only_the_work_that_read_a_beat_it_discards():
    """(review B, 2026-10-08) Restoring checkpoint N takes the story back to
    before beat N, so work queued from beat N-1 read nothing it discards:
    `cancel_from` asks a job to stop only when its read horizon -- its base
    turn, until it reads further -- is at or after N, or unstamped: the
    absence of a stamp is no evidence of anything."""
    def waits(job):
        job.cancelled.wait(3.0)

    earlier = jobs.submit(15, "earlier", waits, base_turn=6)
    same = jobs.submit(15, "same", waits, base_turn=7)
    unstamped = jobs.submit(15, "unstamped", waits)
    assert _wait(lambda: all(j.state == "running" for j in (earlier, same, unstamped)))
    assert jobs.cancel_from(15, "earlier", 7) is None
    assert jobs.cancel_from(15, "same", 7) is same
    assert jobs.cancel_from(15, "unstamped", 7) is unstamped
    assert jobs.cancel_from(15, "absent", 7) is None
    assert _wait(lambda: same.state == "cancelled" and unstamped.state == "cancelled")
    assert earlier.state == "running"
    jobs.cancel(15, "earlier")
    assert _wait(lambda: earlier.state == "cancelled")


def test_a_restore_decides_by_what_a_job_has_read():
    """(review R3-1, 2026-10-08) A job that loops reads later beats than the
    one it was queued from, so a restore deciding by the queued base turn
    left a job that had read the discarded beat running. Its readers raise
    its read horizon before they read (`read_through`), and `cancel_from`
    stops a job whose horizon reaches the restored beat. A job it spares --
    one that read only kept beats -- may finish what it is doing but reads
    none of the beats being played again, until the replayed beat's own
    submit joins it and hands it the new timeline."""
    def waits(job):
        job.cancelled.wait(3.0)

    looping = jobs.submit(16, "looping", waits, base_turn=3)
    assert jobs.read_through(looping, 4) == 4 and looping.read_turn == 4
    assert jobs.read_through(looping, 2) == 2 and looping.read_turn == 4  # never falls
    assert jobs.cancel_from(16, "looping", 4) is looping

    kept = jobs.submit(16, "kept", waits, base_turn=3)
    assert jobs.cancel_from(16, "kept", 4) is None
    assert jobs.spared(kept) and not jobs.is_cancelled(kept)
    assert jobs.read_through(kept, 5) == 3 and kept.read_turn == 3
    assert jobs.submit(16, "kept", waits, base_turn=3) is kept and jobs.spared(kept)
    assert jobs.submit(16, "kept", waits, base_turn=4) is kept and not jobs.spared(kept)
    assert jobs.read_through(kept, 5) == 5 and kept.read_turn == 5

    unstamped = jobs.submit(16, "unstamped", waits)
    assert jobs.read_through(unstamped, 4) == 4 and unstamped.read_turn is None
    assert jobs.cancel_from(16, "unstamped", 9) is unstamped
    assert jobs.read_through(None, 7) == 7 and not jobs.spared(None)
    assert _wait(lambda: looping.state == "cancelled"
                 and unstamped.state == "cancelled")
    kept.cancelled.set()
    assert _wait(lambda: kept.state == "cancelled")


def test_finished_jobs_leave_the_active_table_and_history_is_capped():
    for i in range(jobs._HISTORY_LIMIT + 5):
        job = jobs.submit(5, "k%d" % i, lambda job: True, base_turn=0)
        assert _wait(lambda: job.state == "done")
    assert jobs.active_jobs(5) == []
    assert len(jobs.history(5)) == jobs._HISTORY_LIMIT


def test_two_keys_run_in_parallel():
    # The settled scheduling rule: out-of-band work runs on in parallel. A
    # barrier deadlocks unless both are genuinely in flight at once.
    both = threading.Barrier(2, timeout=3.0)

    def waiter(job):
        both.wait()
        return True

    a = jobs.submit(6, "a", waiter, base_turn=0)
    b = jobs.submit(6, "b", waiter, base_turn=0)
    assert _wait(lambda: a.state == "done" and b.state == "done")


def test_background_work_inherits_the_scheduling_language_context():
    marker = contextvars.ContextVar("job_language_test", default="missing")
    token = marker.set("selected-language")
    try:
        job = jobs.submit(7, "language", lambda _job: marker.get())
    finally:
        marker.reset(token)
    assert _wait(lambda: job.state == "done")
    assert job.result == "selected-language"


def test_background_jobs_do_not_inherit_the_turns_streaming_sinks(temp_db):
    """The context copy exists to carry the story language. It must not also
    carry the live turn's sinks: `schedule_memory_consolidation` is submitted
    from inside the commit step, so an inherited `token_sink` streams a
    background call's tokens into the player's finished turn, and an inherited
    `cancel_event` lets an abort kill the jobs commit just scheduled.
    """
    import queue as queue_module

    from language_runtime import current_language_id
    from core.pipeline_context import current_step_key, current_warning_sink
    from llm.providers import (call_ledger_sink, cancel_event,
                           generation_event_sink, token_sink)

    bus = queue_module.Queue()
    seen = {}
    tokens = [
        token_sink.set(lambda delta: bus.put(delta)),
        generation_event_sink.set(lambda event: bus.put(event)),
        call_ledger_sink.set(lambda **kw: bus.put(kw)),
        cancel_event.set(threading.Event()),
        current_warning_sink.set([]),
        current_step_key.set("commit"),
        current_language_id.set("ja"),
    ]
    try:
        def work(_job):
            seen["token_sink"] = token_sink.get()
            seen["generation_event_sink"] = generation_event_sink.get()
            seen["call_ledger_sink"] = call_ledger_sink.get()
            seen["cancel_event"] = cancel_event.get()
            seen["warning_sink"] = current_warning_sink.get()
            seen["step_key"] = current_step_key.get()
            seen["language"] = current_language_id.get()

        job = jobs.submit(1, "sinks", work)
        assert _wait(lambda: job.state in ("done", "failed"))
    finally:
        for token in reversed(tokens):
            token.var.reset(token)

    # The language is the whole reason the context is copied.
    assert seen["language"] == "ja"
    # Everything scoped to the turn's wall clock is gone.
    assert seen["token_sink"] is None
    assert seen["generation_event_sink"] is None
    assert seen["call_ledger_sink"] is None
    assert seen["cancel_event"] is None
    assert seen["warning_sink"] is None
    assert seen["step_key"] is None
    assert bus.empty()
