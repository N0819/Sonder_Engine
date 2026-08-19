"""A branch must carry every chat-scoped table the checkpoint blob carries.

`web/app.py`'s `turn_branch` names the normalized world tables it copies in a
hand-written tuple, and `_remap_cp_blob` names the ones whose embedded ids it
rewrites in a second hand-written sequence of loops. Neither list is derived
from anything: a table added to `core/db.py` and to the checkpoint blob is
invisible to both until somebody remembers to type its name twice.

`relationship_events` is what that costs. It was added with checkpoint,
archive and delete support and never listed in either place, so branching
dropped every stance's history outright -- and because the checkpoint blob
DOES carry it, the branch's copied checkpoints kept the SOURCE chat's
`frame_id`s, which the first rollback re-inserted. `chat_archive.py`'s own
comment on the same rows says why that is the worse half: reattaching a
grudge to whoever inherited the number "is worse than losing it".

The first test is the class guard: it derives the set of tables from the
schema and the blob, so the next table to be forgotten fails here rather than
in somebody's story. The rest are the instance.
"""

from __future__ import annotations

import json
import time

import pytest

from web import app
from persist.checkpoints import snapshot_state


# Carried into a branch by dedicated code rather than by the `world_tables`
# tuple, so their absence from it is correct: `world` row by row through
# `wset`, `frames`/`chat_personas`/`memories`/`memory_summaries`/`lorebooks`
# each by their own remapping block earlier in `turn_branch`.
_CARRIED_ELSEWHERE = {
    "world", "frames", "chat_personas", "memories", "memory_summaries",
    "lorebooks",
}


def _chat_scoped_tables(db):
    names = [row["name"] for row in db.q(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    scoped = set()
    for name in names:
        if name.startswith("sqlite_"):
            continue
        try:
            cols = db.q(f"PRAGMA table_info({name})")
        except Exception:
            continue
        if any(c["name"] == "chat_id" for c in cols):
            scoped.add(name)
    return scoped


def _blob_world_tables(db, cid):
    """Chat-scoped tables the checkpoint blob carries as row lists.

    Blob order, not sorted: the blob lists a table after the tables its rows
    reference, which is what makes the probe rows below insertable.
    """
    blob = snapshot_state(cid)
    scoped = _chat_scoped_tables(db)
    return [
        key for key, value in blob.items()
        if key in scoped and key not in _CARRIED_ELSEWHERE
        and isinstance(value, list)
    ]


_TURN_FKS = ("turn_id", "created_turn_id", "retired_turn_id")


def _probe_row(db, table, cid, frame_id=None, turn_id=None):
    """Insert one minimally-valid row into `table` for chat `cid`.

    Frame and turn foreign keys are filled with the SOURCE chat's ids -- those
    are the ids a branch has to rewrite, so leaving them NULL would make the
    checkpoint test below pass for the wrong reason. Every other nullable
    column is left NULL.
    """
    cols = db.q(f"PRAGMA table_info({table})")
    names, values = [], []
    for col in cols:
        name = col["name"]
        if name == "chat_id":
            names.append(name)
            values.append(cid)
            continue
        if name == "frame_id" and frame_id is not None:
            names.append(name)
            values.append(frame_id)
            continue
        if name in _TURN_FKS and turn_id is not None:
            names.append(name)
            values.append(turn_id)
            continue
        if col["pk"] and (col["type"] or "").upper() == "INTEGER":
            continue  # rowid alias: let SQLite mint it
        if not col["pk"] and (not col["notnull"]
                              or col["dflt_value"] is not None):
            continue
        kind = (col["type"] or "TEXT").upper()
        if "INT" in kind:
            values.append(0)
        elif "REAL" in kind or "FLOA" in kind or "DOUB" in kind:
            values.append(0.0)
        else:
            values.append("probe")
        names.append(name)
    placeholders = ",".join("?" for _ in names)
    db.qi(f"INSERT INTO {table}({','.join(names)}) VALUES({placeholders})",
          tuple(values))


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Branch source", "", time.time()))
    frame_id = db.qi(
        "INSERT INTO frames(chat_id,label,ordinal,kind,created) "
        "VALUES(?,?,?,?,?)", (cid, "Present", 0, "present", time.time()))
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (cid, 0, "wait", time.time(), frame_id))
    return cid, frame_id, turn_id


def test_branch_carries_every_world_table_the_blob_carries(temp_db):
    """The class. Every chat-scoped table in the checkpoint blob must arrive
    in the branch; a new one added to the schema and the blob but not to
    `turn_branch`'s tuple fails here."""
    cid, frame_id, turn_id = _story(temp_db)
    tables = _blob_world_tables(temp_db, cid)
    assert tables, "no chat-scoped world tables discovered -- probe is broken"
    for table in tables:
        _probe_row(temp_db, table, cid, frame_id, turn_id)

    ncid = app.turn_branch(turn_id)["id"]

    dropped = [
        table for table in tables
        if not temp_db.q(f"SELECT 1 FROM {table} WHERE chat_id=?",
                         (ncid,), one=True)
    ]
    assert dropped == [], (
        "turn_branch dropped chat-scoped world tables: "
        f"{dropped}. Add them to its `world_tables` tuple."
    )


def test_branch_checkpoints_carry_no_foreign_chat_ids(temp_db):
    """The second half. A copied checkpoint may not keep an id that means
    nothing in the branch -- restoring it would re-insert the source chat's
    frames and turns under the branch's own chat_id."""
    cid, frame_id, turn_id = _story(temp_db)
    tables = _blob_world_tables(temp_db, cid)
    for table in tables:
        _probe_row(temp_db, table, cid, frame_id, turn_id)

    ncid = app.turn_branch(turn_id)["id"]

    own_frames = {r["id"] for r in temp_db.q(
        "SELECT id FROM frames WHERE chat_id=?", (ncid,))}
    own_turns = {r["id"] for r in temp_db.q(
        "SELECT id FROM turns WHERE chat_id=?", (ncid,))}
    foreign = []
    for row in temp_db.q("SELECT turn_idx,blob FROM checkpoints WHERE chat_id=?",
                         (ncid,)):
        blob = json.loads(row["blob"])
        for table in tables:
            for entry in blob.get(table) or []:
                for key, allowed in (("frame_id", own_frames),
                                     ("turn_id", own_turns),
                                     ("created_turn_id", own_turns),
                                     ("retired_turn_id", own_turns)):
                    if key in entry and entry[key] is not None \
                            and entry[key] not in allowed:
                        foreign.append((table, key, entry[key]))
    assert foreign == [], (
        "branch checkpoints carry source-chat ids: "
        f"{foreign}. Remap them in _remap_cp_blob."
    )


def test_branch_carries_the_stance_ledger(temp_db):
    """The instance that found the class: a branch of an argument keeps the
    reason for it, rescoped to the branch's own frame."""
    from mind.memory import apply_relationship_updates, relationship_history

    cid, frame_id, turn_id = _story(temp_db)
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
        ("Mora", "{}", time.time()))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,state) VALUES(?,?,?)",
        (cid, char_id, "{}"))
    apply_relationship_updates(cid, char_id, 0, [{
        "target_entity": "Ilse", "trust_delta": -0.2,
        "trigger_event_ids": ["ev:she-lied"],
        "reason": "she lied about the gate"}], frame_id=frame_id)
    assert len(relationship_history(cid, char_id, "Ilse")) == 1

    ncid = app.turn_branch(turn_id)["id"]

    carried = relationship_history(ncid, char_id, "Ilse")
    assert [e["note"] for e in carried] == ["she lied about the gate"]
    row = temp_db.q(
        "SELECT frame_id FROM relationship_events WHERE chat_id=?",
        (ncid,), one=True)
    branch_frames = {r["id"] for r in temp_db.q(
        "SELECT id FROM frames WHERE chat_id=?", (ncid,))}
    assert row["frame_id"] in branch_frames
    assert row["frame_id"] != frame_id


@pytest.fixture(autouse=True)
def _db(temp_db):
    yield temp_db
