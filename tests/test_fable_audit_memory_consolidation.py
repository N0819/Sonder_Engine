"""Regression tests for two more bugs from Fable's whole-codebase audit,
both in memory consolidation (the singleton per-character autobiographical
summary):

B4 -- consolidate_character_memory's SQL query selected candidate
memories by turn_idx alone. turn_idx is GLOBAL play order shared by
every frame, not per-era, so a memory formed during a flash-forward
(tagged with a future frame_id, but still landing inside the ordinary
turn_idx range once play returns to the present) got folded into the
present's autobiographical summary the moment the present's turn_idx
caught up to it -- handing a character knowledge of events they have
not diegetically reached yet. Fixed by filtering candidates through
frames.is_memory_visible, the same epistemic-cursor check every other
memory read path already applies.

B5 -- commit.py's per-character consolidation loop runs on a
concurrent.futures.ThreadPoolExecutor, which (unlike agents/runtime.py's
own bespoke thread-spawning helpers) does not propagate contextvars to
worker threads. maybe_consolidate_character_memory's "frozen to present
only" guard read active_frame_id from inside that worker thread and
always saw the thread-default None there, regardless of which frame's
turn was actually being committed -- silently defeating the guard
during a framed turn's commit. Fixed by passing frame_id explicitly
from the calling thread instead of trusting the contextvar inside the
worker.
"""

from __future__ import annotations

import json
import time

import memory
from character_schema import default_character_data
from frames import create_frame


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_char(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )


class TestConsolidationRespectsFrameVisibility:
    def test_a_future_frames_memory_is_not_folded_into_the_present_summary(
        self, temp_db, monkeypatch
    ):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        memory.add_memory(chat_id, alice, None, "episodic", "witnessed", 0.5,
                          "Ordinary present-day event.", turn_idx=3, frame_id=None)
        memory.add_memory(chat_id, alice, None, "episodic", "witnessed", 0.5,
                          "Saw the paradox unfold in the future.", turn_idx=5, frame_id=future)

        captured = {}

        def fake_chat_complete(role, system, user, **kwargs):
            captured["payload"] = json.loads(user)
            return json.dumps({"summary": "stub", "key_phrases": [], "unresolved_threads": []})

        monkeypatch.setattr(memory, "chat_complete", fake_chat_complete)

        memory.consolidate_character_memory(chat_id, alice, through_turn_idx=10)

        contents = [m["details"] for m in captured["payload"]["memories_chronological"]]
        assert any("present-day" in c for c in contents)
        assert not any("paradox" in c for c in contents)

    def test_a_past_frames_memory_is_visible_to_present_consolidation(
        self, temp_db, monkeypatch
    ):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        past = create_frame(chat_id, label="Past", ordinal=-10, kind="past")

        memory.add_memory(chat_id, alice, None, "episodic", "witnessed", 0.5,
                          "Something that happened long before.", turn_idx=2, frame_id=past)

        captured = {}

        def fake_chat_complete(role, system, user, **kwargs):
            captured["payload"] = json.loads(user)
            return json.dumps({"summary": "stub", "key_phrases": [], "unresolved_threads": []})

        monkeypatch.setattr(memory, "chat_complete", fake_chat_complete)

        memory.consolidate_character_memory(chat_id, alice, through_turn_idx=10)

        contents = [m["details"] for m in captured["payload"]["memories_chronological"]]
        assert any("long before" in c for c in contents)


class TestMaybeConsolidateFrameGuardSurvivesThreadPool:
    def test_explicit_frame_id_freezes_consolidation_even_though_ambient_context_is_present(
        self, temp_db, monkeypatch
    ):
        """Simulates exactly what a ThreadPoolExecutor worker sees: the
        ambient active_frame_id contextvar reads back as None (the
        thread-default) even though the turn actually being committed
        belongs to a real frame. Before the fix, this meant consolidation
        would run for real here; the explicit frame_id kwarg must
        override the (wrong) ambient default."""
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        # Present-tagged (visible-from-anywhere) memories on purpose --
        # this test isolates B5 (the guard reading the wrong ambient
        # frame) from B4 (visibility filtering), which would otherwise
        # shield the scenario for an unrelated reason (nothing visible
        # to summarize) and mask whether the guard itself was honored.
        for i in range(45):
            memory.add_memory(chat_id, alice, None, "episodic", "witnessed", 0.5,
                              f"Event {i}.", turn_idx=i, frame_id=None)

        def boom(*a, **k):
            raise AssertionError("consolidation must not run while frozen to a real frame")

        monkeypatch.setattr(memory, "chat_complete", boom)

        from db import active_frame_id
        assert active_frame_id.get() is None  # the ambient default, as in a bare worker thread

        result = memory.maybe_consolidate_character_memory(
            chat_id, alice, current_turn_idx=50, frame_id=future,
        )
        assert result is None

    def test_explicit_none_frame_id_still_allows_consolidation(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")

        for i in range(45):
            memory.add_memory(chat_id, alice, None, "episodic", "witnessed", 0.5,
                              f"Event {i}.", turn_idx=i, frame_id=None)

        monkeypatch.setattr(
            memory, "chat_complete",
            lambda *a, **k: json.dumps({"summary": "ok", "key_phrases": [], "unresolved_threads": []}),
        )

        result = memory.maybe_consolidate_character_memory(
            chat_id, alice, current_turn_idx=50, frame_id=None,
        )
        assert result is not None
        assert result["summary"] == "ok"
