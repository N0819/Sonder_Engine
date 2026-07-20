"""Regression tests for the 2026-07 app.py audit fixes.

1. ``turn_branch`` performed ~10 phases of inserts (frames, chat_chars,
   turns/steps/variants, memories, lorebooks, world, checkpoints) through
   autocommitting ``qi()`` with no enclosing transaction -- unlike
   ``chat_import``, which wraps the equivalent work.  A mid-branch
   exception therefore left a visible, half-built, corrupt chat behind.
   It now mirrors chat_import: everything from the new ``chats`` row
   through the final checkpoint insert commits atomically.

2. ``turn_del`` restored the turn's checkpoint BEFORE (outside) the
   delete transaction, so a failed delete left the chat rewound to the
   turn's start while the turn and its steps still existed.  The restore
   now runs inside the same transaction as the deletes.

3. Host-surface validation nits that returned 500 on garbage input:
   ``mem_add``'s bare ``float(salience)`` cast, ``dlg_put``'s bare
   ``int()``/``float()`` casts, and ``attach_lore``'s missing
   chat-existence check (previously an FK IntegrityError on a bad cid).
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi import HTTPException

import app
import memory
from character_schema import default_character_data
from checkpoints import ensure_checkpoint


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


def _make_turn(db, chat_id, idx=0):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "do something", time.time()),
    )


def _add_step(db, turn_id, key="narrator", ord_=0):
    sid = db.qi(
        "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
        (turn_id, key, key, ord_),
    )
    db.qi(
        "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
        (sid, json.dumps({"prose": "hello"}), time.time()),
    )
    return sid


# Every table turn_branch writes to (directly or through helpers), so a
# rolled-back branch can be asserted to have left NOTHING anywhere.
_TABLES = (
    "chats", "frames", "turns", "steps", "variants", "events",
    "chat_chars", "chat_char_frames", "memories", "memory_summaries",
    "lorebooks", "chat_lorebooks", "lore_entries", "world", "checkpoints",
)


def _row_counts(db):
    return {
        t: db.q(f"SELECT COUNT(*) AS n FROM {t}", one=True)["n"]
        for t in _TABLES
    }


# ---- bug 1: turn_branch was not transactional ----

class TestTurnBranchAtomicity:
    def _seed_branchable_chat(self, db):
        chat_id = _make_chat(db)
        char_id = _make_char(db, "Alice")
        db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,'active','{}')",
            (chat_id, char_id),
        )
        db.wset(chat_id, "scene", {"location": "Kitchen"})
        turn_id = _make_turn(db, chat_id, idx=0)
        _add_step(db, turn_id)
        memory.add_memory(
            chat_id, char_id, turn_id, "episodic", "witnessed", 0.5,
            "Something happened.", turn_idx=0,
        )
        ensure_checkpoint(chat_id, 0)
        return chat_id, turn_id

    def test_mid_branch_failure_leaves_no_partial_chat(self, temp_db, monkeypatch):
        chat_id, turn_id = self._seed_branchable_chat(temp_db)
        before = _row_counts(temp_db)

        def boom(*args, **kwargs):
            raise RuntimeError("mid-branch failure")

        # _remap_cp_blob runs in the LAST phase of turn_branch (checkpoint
        # copying) -- by the time it raises, the new chat plus its frames,
        # chat_chars, turns/steps/variants, memories, lorebooks, and world
        # rows have all already been written.  Pre-fix, all of those
        # survived the exception as a visible corrupt chat.
        monkeypatch.setattr(app, "_remap_cp_blob", boom)

        with pytest.raises(RuntimeError, match="mid-branch failure"):
            app.turn_branch(turn_id)

        assert _row_counts(temp_db) == before
        assert [r["id"] for r in temp_db.q("SELECT id FROM chats")] == [chat_id]

    def test_branch_success_path_unchanged(self, temp_db):
        chat_id, turn_id = self._seed_branchable_chat(temp_db)

        branched = app.turn_branch(turn_id)
        ncid = branched["id"]

        assert ncid != chat_id
        turns = temp_db.q(
            "SELECT id, idx, player_input FROM turns WHERE chat_id=?", (ncid,)
        )
        assert len(turns) == 1
        assert turns[0]["idx"] == 0
        assert turns[0]["player_input"] == "do something"
        steps = temp_db.q(
            "SELECT id FROM steps WHERE turn_id=?", (turns[0]["id"],)
        )
        assert len(steps) == 1
        assert temp_db.q(
            "SELECT 1 FROM variants WHERE step_id=? AND active=1",
            (steps[0]["id"],), one=True,
        )
        assert temp_db.wget(ncid, "scene") == {"location": "Kitchen"}
        assert temp_db.q(
            "SELECT COUNT(*) AS n FROM memories WHERE chat_id=?", (ncid,), one=True
        )["n"] == 1
        # Final checkpoint snapshot for the branched chat lands at idx+1.
        assert temp_db.q(
            "SELECT 1 FROM checkpoints WHERE chat_id=? AND turn_idx=?",
            (ncid, 1), one=True,
        )


# ---- bug 2: turn_del restored the checkpoint outside the delete tx ----

class TestTurnDelAtomicity:
    def _seed_deletable_turn(self, db):
        chat_id = _make_chat(db)
        db.wset(chat_id, "flag", "before")
        # Checkpoint at the turn's start captures flag == "before" ...
        ensure_checkpoint(chat_id, 0)
        turn_id = _make_turn(db, chat_id, idx=0)
        _add_step(db, turn_id)
        # ... then the turn "changes" the world.
        db.wset(chat_id, "flag", "after")
        return chat_id, turn_id

    def test_failed_delete_rolls_back_the_checkpoint_restore(self, temp_db, monkeypatch):
        chat_id, turn_id = self._seed_deletable_turn(temp_db)

        def boom(*args, **kwargs):
            raise RuntimeError("delete failed")

        # delete_turn_memories runs mid-way through the delete phase.
        # Pre-fix, the checkpoint restore had already committed separately,
        # so this failure left the chat rewound WHILE the turn still
        # existed.  Now restore + deletes are one transaction: everything
        # must roll back together.
        monkeypatch.setattr(app, "delete_turn_memories", boom)

        with pytest.raises(RuntimeError, match="delete failed"):
            app.turn_del(turn_id)

        assert temp_db.q("SELECT 1 FROM turns WHERE id=?", (turn_id,), one=True)
        assert temp_db.q(
            "SELECT COUNT(*) AS n FROM steps WHERE turn_id=?", (turn_id,), one=True
        )["n"] == 1
        # The world must NOT have been rewound to the turn's start.
        assert temp_db.wget(chat_id, "flag") == "after"
        # And the checkpoint survives for a later retry.
        assert temp_db.q(
            "SELECT 1 FROM checkpoints WHERE chat_id=? AND turn_idx=0",
            (chat_id,), one=True,
        )

    def test_successful_delete_still_restores_and_removes_rows(self, temp_db):
        chat_id, turn_id = self._seed_deletable_turn(temp_db)

        assert app.turn_del(turn_id) == {"ok": True}

        assert temp_db.q("SELECT 1 FROM turns WHERE id=?", (turn_id,), one=True) is None
        assert temp_db.q("SELECT COUNT(*) AS n FROM steps", one=True)["n"] == 0
        assert temp_db.q("SELECT COUNT(*) AS n FROM variants", one=True)["n"] == 0
        assert temp_db.wget(chat_id, "flag") == "before"
        assert temp_db.q(
            "SELECT 1 FROM checkpoints WHERE chat_id=?", (chat_id,), one=True
        ) is None


# ---- bug 3: garbage input returned 500 instead of 400/404 ----

class TestValidationStatusCodes:
    def test_mem_add_rejects_non_numeric_salience(self, temp_db):
        chat_id = _make_chat(temp_db)
        char_id = _make_char(temp_db, "Alice")

        with pytest.raises(HTTPException) as exc_info:
            app.mem_add(chat_id, char_id, {"salience": "very", "content": "x"})

        assert exc_info.value.status_code == 400
        assert temp_db.q("SELECT COUNT(*) AS n FROM memories", one=True)["n"] == 0

    def test_mem_add_success_path_unchanged(self, temp_db):
        chat_id = _make_chat(temp_db)
        char_id = _make_char(temp_db, "Alice")

        # float() previously accepted numeric strings too -- still must.
        out = app.mem_add(chat_id, char_id, {"salience": "0.7", "content": "Remembered."})

        assert isinstance(out["id"], int)
        row = temp_db.q("SELECT salience FROM memories WHERE id=?", (out["id"],), one=True)
        assert row["salience"] == pytest.approx(0.7)

    @pytest.mark.parametrize("body", [
        {"autonomy": "high"},
        {"min_lines": "many"},
        {"max_lines": None},
        {"variance": "wobbly"},
    ])
    def test_dlg_put_rejects_non_numeric_fields(self, temp_db, body):
        chat_id = _make_chat(temp_db)

        with pytest.raises(HTTPException) as exc_info:
            app.dlg_put(chat_id, body)

        assert exc_info.value.status_code == 400

    def test_dlg_put_success_path_unchanged(self, temp_db):
        chat_id = _make_chat(temp_db)

        config = app.dlg_put(chat_id, {"autonomy": 70, "min_lines": 1, "max_lines": 3})

        assert config["autonomy"] == 70
        assert config["min_lines"] == 1
        assert config["max_lines"] == 3
        assert temp_db.wget(chat_id, "dialogue_config") == config

    def test_attach_lore_missing_chat_is_404_not_integrity_error(self, temp_db):
        book = temp_db.qi("INSERT INTO lorebooks(name) VALUES('Global book')")

        with pytest.raises(HTTPException) as exc_info:
            app.attach_lore(99999, {"lorebook_id": book})

        assert exc_info.value.status_code == 404
        assert temp_db.q(
            "SELECT COUNT(*) AS n FROM chat_lorebooks", one=True
        )["n"] == 0

    def test_attach_lore_success_path_unchanged(self, temp_db):
        chat_id = _make_chat(temp_db)
        book = temp_db.qi("INSERT INTO lorebooks(name) VALUES('Global book')")

        out = app.attach_lore(chat_id, {"lorebook_id": book})

        assert out["lorebook_id"]
        assert temp_db.q(
            "SELECT 1 FROM chat_lorebooks WHERE chat_id=? AND lorebook_id=?",
            (chat_id, out["lorebook_id"]), one=True,
        )
