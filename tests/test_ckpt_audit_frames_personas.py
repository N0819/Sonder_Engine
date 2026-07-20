"""Checkpoint audit finding 1: snapshot/restore must cover `frames`
rows and `chat_personas` stations, which spatial split/merge commits
durably mutate (spatial_frames.perform_split/perform_merge). Without
them, rerolling a split/merge turn leaves stranded personas and
permanently-merged frames."""

import json
import time

import pytest

from character_schema import default_character_data
from checkpoints import ensure_checkpoint, restore_checkpoint, snapshot_state
from frames import create_frame


def _chat_char_persona(db):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        ("Alice", json.dumps(default_character_data("Alice")), "{}", time.time(), "char_alice"),
    )
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Player Two", "{}", "{}"),
    )
    db.qi(
        "INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) VALUES(?,?,?,?)",
        (chat_id, persona_id, "active", None),
    )
    return chat_id, char_id, persona_id


def test_snapshot_state_includes_frames_and_chat_personas(temp_db):
    chat_id, char_id, persona_id = _chat_char_persona(temp_db)
    frame_id = create_frame(chat_id, label="past era", ordinal=-1, kind="past")
    temp_db.qi(
        "UPDATE chat_personas SET frame_id=? WHERE chat_id=? AND persona_id=?",
        (frame_id, chat_id, persona_id),
    )

    snap = snapshot_state(chat_id)

    assert "frames" in snap
    assert "chat_personas" in snap
    assert [f["id"] for f in snap["frames"]] == [frame_id]
    assert snap["frames"][0]["kind"] == "past"
    assert snap["frames"][0]["ordinal"] == -1
    assert snap["chat_personas"] == [
        {"persona_id": persona_id, "status": "active", "frame_id": frame_id}
    ]


def test_restore_reverts_split_frame_persona_station_and_merge_mark(temp_db):
    chat_id, char_id, persona_id = _chat_char_persona(temp_db)

    # Pre-checkpoint era, with a committed turn played in it: restoring
    # must never disturb this frame or the turn's assignment to it.
    pre_fid = create_frame(chat_id, label="past era", ordinal=-1, kind="past")
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
        (chat_id, 0, "look around", time.time(), pre_fid),
    )

    ensure_checkpoint(chat_id, 1)

    # Simulate the durable effects of a spatial split committed at this
    # turn (what perform_split does): a new frame row, the persona
    # restationed into it, a cast overlay row -- plus a merge marker
    # stamped onto the pre-existing frame (what perform_merge does).
    away_fid = create_frame(
        chat_id, label="Away — garden", ordinal=0, kind="spatial",
        parent_frame_id=None, split_turn_idx=1,
    )
    temp_db.qi(
        "UPDATE chat_personas SET frame_id=? WHERE chat_id=? AND persona_id=?",
        (away_fid, chat_id, persona_id),
    )
    temp_db.qi(
        "INSERT INTO chat_char_frames(chat_id,char_id,frame_id,status,state) VALUES(?,?,?,?,?)",
        (chat_id, char_id, away_fid, "active", "{}"),
    )
    temp_db.qi("UPDATE frames SET merged_turn_idx=? WHERE id=?", (7, pre_fid))

    restore_checkpoint(chat_id, 1)

    frame_rows = temp_db.q("SELECT * FROM frames WHERE chat_id=?", (chat_id,))
    assert [r["id"] for r in frame_rows] == [pre_fid], (
        "the frame inserted by the rerolled split must be gone"
    )
    assert frame_rows[0]["merged_turn_idx"] is None, (
        "the merge marker stamped after the checkpoint must be reverted"
    )

    persona_row = temp_db.q(
        "SELECT * FROM chat_personas WHERE chat_id=? AND persona_id=?",
        (chat_id, persona_id), one=True,
    )
    assert persona_row is not None
    assert persona_row["frame_id"] is None, "persona must be re-stationed to the present"
    assert persona_row["status"] == "active"

    assert temp_db.q("SELECT COUNT(*) AS c FROM chat_char_frames WHERE chat_id=?",
                     (chat_id,), one=True)["c"] == 0

    turn_row = temp_db.q("SELECT frame_id FROM turns WHERE id=?", (turn_id,), one=True)
    assert turn_row["frame_id"] == pre_fid, (
        "restore must not null out pre-checkpoint turns' frame assignment "
        "(frames restore must not delete-and-reinsert surviving frames "
        "under ON DELETE SET NULL)"
    )


def test_restore_reinserts_frames_deleted_after_checkpoint(temp_db):
    chat_id, char_id, persona_id = _chat_char_persona(temp_db)
    fid = create_frame(chat_id, label="future era", ordinal=3, kind="future")
    temp_db.qi(
        "UPDATE chat_personas SET frame_id=? WHERE chat_id=? AND persona_id=?",
        (fid, chat_id, persona_id),
    )
    temp_db.qi(
        "INSERT INTO chat_char_frames(chat_id,char_id,frame_id,status,state) VALUES(?,?,?,?,?)",
        (chat_id, char_id, fid, "dormant", "{}"),
    )
    ensure_checkpoint(chat_id, 2)

    temp_db.qi("DELETE FROM frames WHERE id=?", (fid,))
    restore_checkpoint(chat_id, 2)

    row = temp_db.q("SELECT * FROM frames WHERE chat_id=?", (chat_id,), one=True)
    assert row is not None and row["id"] == fid
    assert row["label"] == "future era"
    assert row["ordinal"] == 3
    cf = temp_db.q("SELECT * FROM chat_char_frames WHERE chat_id=?", (chat_id,), one=True)
    assert cf is not None and cf["frame_id"] == fid and cf["status"] == "dormant"
    persona_row = temp_db.q(
        "SELECT frame_id FROM chat_personas WHERE chat_id=? AND persona_id=?",
        (chat_id, persona_id), one=True,
    )
    assert persona_row["frame_id"] == fid


def test_legacy_checkpoint_without_frame_keys_leaves_frames_alone(temp_db):
    chat_id, char_id, persona_id = _chat_char_persona(temp_db)
    ensure_checkpoint(chat_id, 3)

    # Strip the new keys, simulating a checkpoint written before they existed.
    row = temp_db.q(
        "SELECT * FROM checkpoints WHERE chat_id=? AND turn_idx=?", (chat_id, 3), one=True
    )
    blob = json.loads(row["blob"])
    blob.pop("frames", None)
    blob.pop("chat_personas", None)
    temp_db.qi("UPDATE checkpoints SET blob=? WHERE id=?", (json.dumps(blob), row["id"]))

    fid = create_frame(chat_id, label="post-checkpoint era", ordinal=1, kind="future")
    temp_db.qi(
        "UPDATE chat_personas SET frame_id=? WHERE chat_id=? AND persona_id=?",
        (fid, chat_id, persona_id),
    )

    restore_checkpoint(chat_id, 3)

    assert temp_db.q("SELECT COUNT(*) AS c FROM frames WHERE chat_id=?",
                     (chat_id,), one=True)["c"] == 1
    persona_row = temp_db.q(
        "SELECT frame_id FROM chat_personas WHERE chat_id=? AND persona_id=?",
        (chat_id, persona_id), one=True,
    )
    assert persona_row["frame_id"] == fid
