"""Regression tests for Stage B's recompute relaxation: _require_latest
now means "latest turn of ITS OWN FRAME, and no other frame has advanced
past it" -- not "the single latest turn in the whole chat." This is what
lets two frames each reroll their own most recent turn independently,
while still refusing (with a clear reason) exactly when that would
silently roll back a different frame's genuinely newer progress, since
checkpoints/memories/cast/world_entities remain chat-global rather than
frame-sliced.
"""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

import app
from frames import create_frame


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_turn(db, chat_id, idx, frame_id=None):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
        (chat_id, idx, "go", time.time(), frame_id),
    )


class TestRequireLatestIsFrameAware:
    def test_frame_latest_turn_with_no_other_frame_progress_is_recomputable(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=0)
        turn = temp_db.q("SELECT * FROM turns WHERE id=?", (turn_id,), one=True)
        app._require_latest(dict(turn))  # does not raise

    def test_a_later_turn_in_the_same_frame_blocks_recompute(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn1_id = _make_turn(temp_db, chat_id, idx=0)
        _make_turn(temp_db, chat_id, idx=1)
        turn1 = dict(temp_db.q("SELECT * FROM turns WHERE id=?", (turn1_id,), one=True))

        with pytest.raises(HTTPException) as exc_info:
            app._require_latest(turn1)
        assert exc_info.value.status_code == 409
        assert "this frame" in exc_info.value.detail

    def test_a_different_frames_later_turn_does_not_block_this_frames_latest(self, temp_db):
        """The actual Stage B deliverable: frame A's own latest turn stays
        recomputable even though frame B has since advanced further,
        PROVIDED frame B's turns are not later in play order than frame
        A's turn being recomputed."""
        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        # Frame A's turn happens FIRST in play order, frame B's SECOND --
        # but recomputing A's turn is what's under test, and nothing in
        # frame B exists yet at that point... to actually test "another
        # frame advanced past," B's turn must have a LATER idx.
        turn_a_id = _make_turn(temp_db, chat_id, idx=0, frame_id=None)
        _make_turn(temp_db, chat_id, idx=1, frame_id=future)
        turn_a = dict(temp_db.q("SELECT * FROM turns WHERE id=?", (turn_a_id,), one=True))

        with pytest.raises(HTTPException) as exc_info:
            app._require_latest(turn_a)
        assert "Another frame has advanced" in exc_info.value.detail

    def test_recompute_is_allowed_when_the_other_frames_turns_are_all_earlier(self, temp_db):
        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        _make_turn(temp_db, chat_id, idx=0, frame_id=future)
        turn_a_id = _make_turn(temp_db, chat_id, idx=1, frame_id=None)
        turn_a = dict(temp_db.q("SELECT * FROM turns WHERE id=?", (turn_a_id,), one=True))

        app._require_latest(turn_a)  # does not raise -- future's turn is EARLIER in play order

    def test_pipeline_get_reports_blocked_by_other_frame(self, temp_db):
        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        turn_a_id = _make_turn(temp_db, chat_id, idx=0, frame_id=None)
        _make_turn(temp_db, chat_id, idx=1, frame_id=future)

        result = app.pipeline_get(turn_a_id)
        assert result["editable"] is False
        assert result["blocked_by_other_frame"] is True
        assert result["resume_key"] is None

    def test_pipeline_get_is_editable_when_no_other_frame_blocks_it(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn_id = _make_turn(temp_db, chat_id, idx=0)
        result = app.pipeline_get(turn_id)
        assert result["editable"] is True
        assert result["blocked_by_other_frame"] is False

    def test_step_mutation_also_respects_the_relaxed_frame_check(self, temp_db):
        """step_edit/step_activate route through _require_step_turn ->
        _require_latest -- confirm the SAME relaxed semantics apply
        there, not just to whole-turn reroll/rerun."""
        from agents.storage import save_step

        chat_id = _make_chat(temp_db)
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        turn_a_id = _make_turn(temp_db, chat_id, idx=0, frame_id=None)
        sid, _, _ = save_step(turn_a_id, "narrator", "Narrator", 0, {"prose": "a"})
        _make_turn(temp_db, chat_id, idx=1, frame_id=future)

        with pytest.raises(HTTPException) as exc_info:
            app.step_edit(sid, {"content": {"prose": "b"}})
        assert exc_info.value.status_code == 409
