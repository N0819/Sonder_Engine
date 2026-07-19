"""Coverage for the chat_char_frames overlay table, which lets a
character's status/state genuinely diverge between frames -- e.g. active
and calm in the present while dormant and terrified in a future frame
that has already lived through a paradox. Mirrors the "ledger + cursor,
fallback to base row" pattern already used for world state and
memories (see frames.py's module docstring).
"""

from __future__ import annotations

import json
import time

import app
from checkpoints import restore_checkpoint, snapshot_state
from pipeline_context import ChatData, PipelineContext, TurnData
from scene import active_cast, private_knowledge_for, set_char_state, set_char_status
from commit import commit_cast_changes


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_char(db, name, private_history=None):
    sheet = {"identity": {"name": name}}
    if private_history is not None:
        sheet["private_history"] = private_history
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time()),
    )


def _add_to_chat(db, chat_id, char_id, status="active", state=None):
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, status, json.dumps(state or {})),
    )


class TestSetCharStatusAndState:
    def test_present_write_updates_the_base_row_directly(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        _add_to_chat(temp_db, chat_id, alice, status="active", state={"mood": "calm"})

        set_char_status(chat_id, alice, "dormant", frame_id=None)
        set_char_state(chat_id, alice, json.dumps({"mood": "terrified"}), frame_id=None)

        row = temp_db.q("SELECT * FROM chat_chars WHERE chat_id=? AND char_id=?",
                         (chat_id, alice), one=True)
        assert row["status"] == "dormant"
        assert json.loads(row["state"]) == {"mood": "terrified"}
        overlay = temp_db.q("SELECT * FROM chat_char_frames WHERE chat_id=?", (chat_id,))
        assert overlay == []

    def test_frame_write_creates_an_overlay_without_touching_the_base_row(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        _add_to_chat(temp_db, chat_id, alice, status="active", state={"mood": "calm"})
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})

        set_char_status(chat_id, alice, "dormant", frame_id=future["id"])

        base = temp_db.q("SELECT * FROM chat_chars WHERE chat_id=? AND char_id=?",
                          (chat_id, alice), one=True)
        assert base["status"] == "active"
        assert json.loads(base["state"]) == {"mood": "calm"}

        overlay = temp_db.q(
            "SELECT * FROM chat_char_frames WHERE chat_id=? AND char_id=? AND frame_id=?",
            (chat_id, alice, future["id"]), one=True,
        )
        assert overlay["status"] == "dormant"
        # status-only write seeds state from the base row rather than
        # clobbering it with an empty default.
        assert json.loads(overlay["state"]) == {"mood": "calm"}

    def test_frame_state_write_after_status_write_does_not_clobber_status(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        _add_to_chat(temp_db, chat_id, alice, status="active", state={"mood": "calm"})
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})

        set_char_status(chat_id, alice, "dormant", frame_id=future["id"])
        set_char_state(chat_id, alice, json.dumps({"mood": "terrified"}), frame_id=future["id"])

        overlay = temp_db.q(
            "SELECT * FROM chat_char_frames WHERE chat_id=? AND char_id=? AND frame_id=?",
            (chat_id, alice, future["id"]), one=True,
        )
        assert overlay["status"] == "dormant"
        assert json.loads(overlay["state"]) == {"mood": "terrified"}


class TestActiveCastIsFrameAware:
    def test_a_character_can_be_active_in_present_and_dormant_in_a_future_frame(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        _add_to_chat(temp_db, chat_id, alice, status="active", state={"mood": "calm"})
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        set_char_status(chat_id, alice, "dormant", frame_id=future["id"])

        present_cast = active_cast(chat_id, frame_id=None)
        assert [c["id"] for c in present_cast] == [alice]

        future_cast = active_cast(chat_id, frame_id=future["id"])
        assert future_cast == []

    def test_an_untouched_frame_falls_back_to_the_base_row(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        _add_to_chat(temp_db, chat_id, alice, status="active", state={"mood": "calm"})
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})

        future_cast = active_cast(chat_id, frame_id=future["id"])
        assert [c["id"] for c in future_cast] == [alice]
        assert json.loads(future_cast[0]["cstate"]) == {"mood": "calm"}


class TestPrivateKnowledgeIsFrameAware:
    def test_private_history_divergence_between_frames(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        _add_to_chat(temp_db, chat_id, alice, status="active", state={
            "private_history": [{"about": "Alice", "content": "I feel fine.", "known_by": ["alice"]}]
        })
        chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True))
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})

        set_char_state(chat_id, alice, json.dumps({
            "private_history": [{"about": "Alice", "content": "I survived the paradox.",
                                  "known_by": ["alice"]}]
        }), frame_id=future["id"])

        present_knowledge = private_knowledge_for(chat, "Alice", frame_id=None)
        assert present_knowledge[0]["content"] == "I feel fine."

        future_knowledge = private_knowledge_for(chat, "Alice", frame_id=future["id"])
        assert future_knowledge[0]["content"] == "I survived the paradox."


class TestCommitCastChangesIsFrameAware:
    def test_a_status_change_committed_in_a_future_frame_does_not_affect_the_present(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        _add_to_chat(temp_db, chat_id, alice, status="active", state={})
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})

        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 1, "go dormant", time.time(), future["id"]),
        )
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                          scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="go dormant",
                          created=time.time(), frame_id=future["id"]),
            cast=[], input="go dormant",
        )
        ctx.director_resolve = {
            "state_diff": {"cast_changes": [{"who": "Alice", "status": "dormant"}]}
        }

        commit_cast_changes(ctx, nonce=0)

        base = temp_db.q("SELECT status FROM chat_chars WHERE chat_id=? AND char_id=?",
                          (chat_id, alice), one=True)
        assert base["status"] == "active"

        overlay = temp_db.q(
            "SELECT status FROM chat_char_frames WHERE chat_id=? AND char_id=? AND frame_id=?",
            (chat_id, alice, future["id"]), one=True,
        )
        assert overlay["status"] == "dormant"


class TestCheckpointRoundTrip:
    def test_snapshot_and_restore_preserve_frame_overlays(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        _add_to_chat(temp_db, chat_id, alice, status="active", state={"mood": "calm"})
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        set_char_status(chat_id, alice, "dormant", frame_id=future["id"])
        set_char_state(chat_id, alice, json.dumps({"mood": "terrified"}), frame_id=future["id"])

        blob = snapshot_state(chat_id)
        assert blob["char_frames"] == [
            {"char_id": alice, "frame_id": future["id"], "status": "dormant",
             "state": {"mood": "terrified"}}
        ]

        temp_db.qi("DELETE FROM chat_char_frames WHERE chat_id=?", (chat_id,))
        temp_db.qi(
            "INSERT INTO checkpoints(chat_id,turn_idx,blob,created) VALUES(?,?,?,?)",
            (chat_id, 0, json.dumps(blob), time.time()),
        )
        restore_checkpoint(chat_id, 0)

        overlay = temp_db.q(
            "SELECT * FROM chat_char_frames WHERE chat_id=? AND char_id=? AND frame_id=?",
            (chat_id, alice, future["id"]), one=True,
        )
        assert overlay["status"] == "dormant"
        assert json.loads(overlay["state"]) == {"mood": "terrified"}


class TestBranchCloningIncludesCharFrames:
    def test_branching_clones_the_overlay_with_a_remapped_frame_id(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        _add_to_chat(temp_db, chat_id, alice, status="active", state={"mood": "calm"})
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 0, "start", time.time()),
        )
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        set_char_status(chat_id, alice, "dormant", frame_id=future["id"])
        set_char_state(chat_id, alice, json.dumps({"mood": "terrified"}), frame_id=future["id"])

        branched = app.turn_branch(turn_id)
        ncid = branched["id"]

        cloned_frames = app.frames_list(ncid)["frames"]
        cloned_future = next(f for f in cloned_frames if f["label"] == "Future")

        overlay = temp_db.q(
            "SELECT * FROM chat_char_frames WHERE chat_id=? AND frame_id=?",
            (ncid, cloned_future["id"]), one=True,
        )
        assert overlay is not None
        assert overlay["status"] == "dormant"
        assert json.loads(overlay["state"]) == {"mood": "terrified"}
        assert overlay["frame_id"] != future["id"]


class TestExportImportRoundTripsCharFrames:
    def test_export_then_import_preserves_the_overlay(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        _add_to_chat(temp_db, chat_id, alice, status="active", state={"mood": "calm"})
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        set_char_status(chat_id, alice, "dormant", frame_id=future["id"])
        set_char_state(chat_id, alice, json.dumps({"mood": "terrified"}), frame_id=future["id"])

        exported = app.chat_export(chat_id)
        assert len(exported["char_frames"]) == 1

        alice_sheet = json.loads(temp_db.q(
            "SELECT sheet FROM characters WHERE id=?", (alice,), one=True)["sheet"])
        exported["resources"] = {
            "characters": [{"old_id": alice, "sheet": alice_sheet, "source": {}}],
        }

        result = app.chat_import({"data": exported})
        new_chat_id = result["id"]

        new_frames = app.frames_list(new_chat_id)["frames"]
        new_future = next(f for f in new_frames if f["label"] == "Future")

        overlay = temp_db.q(
            "SELECT * FROM chat_char_frames WHERE chat_id=? AND frame_id=?",
            (new_chat_id, new_future["id"]), one=True,
        )
        assert overlay is not None
        assert overlay["status"] == "dormant"
        assert json.loads(overlay["state"]) == {"mood": "terrified"}
