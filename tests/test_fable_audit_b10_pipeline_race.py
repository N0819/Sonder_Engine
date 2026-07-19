"""Regression test for B10 from Fable's audit: app.py's _require_frame_idle
(and _require_chat_idle) check ABORTS, then LATER begin_pipeline
unconditionally registers -- a gap in which two near-simultaneous
requests for the SAME (chat_id, frame_id) could both pass the check and
both register, with the second's Event silently clobbering the first's
in ABORTS. That left the first pipeline unabortable and let two
pipelines run against the same frame at once, exactly what the
(chat_id, frame_id) keying scheme exists to prevent.

Fixed by making begin_pipeline's check-then-register atomic under a
lock, raising PipelineBusyError instead of overwriting when a
concurrent request already won the race.
"""

from __future__ import annotations

import threading
import time

import pytest

from agents.runtime import ABORTS, PipelineBusyError, begin_pipeline


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


class TestBeginPipelineClosesTheRace:
    def test_a_second_call_for_the_same_slot_raises_instead_of_overwriting(self, temp_db):
        chat_id = _make_chat(temp_db)
        first = begin_pipeline(chat_id, None)
        try:
            with pytest.raises(PipelineBusyError):
                begin_pipeline(chat_id, None)
            # The first Event must still be the one registered -- a
            # second, silently-overwriting call would have made it
            # unabortable.
            assert ABORTS[(chat_id, None)] is first
        finally:
            ABORTS.pop((chat_id, None), None)

    def test_a_different_frame_is_unaffected(self, temp_db):
        chat_id = _make_chat(temp_db)
        present = begin_pipeline(chat_id, None)
        try:
            future = begin_pipeline(chat_id, 999)
            try:
                assert present is not future
            finally:
                ABORTS.pop((chat_id, 999), None)
        finally:
            ABORTS.pop((chat_id, None), None)

    def test_many_concurrent_attempts_for_the_same_slot_exactly_one_wins(self, temp_db):
        chat_id = _make_chat(temp_db)
        winners = []
        errors = []
        lock = threading.Lock()

        def attempt():
            try:
                abort = begin_pipeline(chat_id, None)
                with lock:
                    winners.append(abort)
            except PipelineBusyError:
                with lock:
                    errors.append(True)

        threads = [threading.Thread(target=attempt) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        try:
            assert len(winners) == 1
            assert len(errors) == 19
        finally:
            ABORTS.pop((chat_id, None), None)
