"""The queue offscreen work runs on.

What it must guarantee is that a turn is never blocked by background work,
never failed by it, and never handed a result computed against a world that
has since moved. No database: scheduling is not a storage question, and these
run without ENGINE_DB.
"""

import threading
import time

import pytest

import jobs


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


def test_a_result_computed_before_the_story_moved_is_stale():
    job = jobs.submit(3, "tick", lambda job: "ok", base_turn=7)
    assert _wait(lambda: job.state == "done")
    assert jobs.is_stale(job, 7) is False
    assert jobs.is_stale(job, 8) is True


def test_an_unstamped_job_is_not_reported_fresh():
    job = jobs.submit(3, "unstamped", lambda job: "ok")
    assert _wait(lambda: job.state == "done")
    assert jobs.is_stale(job, 99) is False
    assert job.base_turn is None


def test_cancelling_files_the_job_as_cancelled_rather_than_done():
    def cooperative(job):
        job.cancelled.wait(3.0)
        return "partial"

    job = jobs.submit(4, "tick", cooperative, base_turn=2)
    assert _wait(lambda: job.state == "running")
    assert jobs.cancel_chat(4) == 1
    assert _wait(lambda: job.state == "cancelled")
    assert jobs.status(4, "tick") == "cancelled"


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
