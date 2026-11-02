"""An absent mind's memories come through the one seam every mind reads by.

`world.offscreen.agent_context` builds the paid off-screen tick's private
context, and its docstring names the failure it exists to prevent: "how did
he know that". It filtered the mind's theory-of-mind ledger by frame, and read
its memories with plain SQL -- the newest twelve by play order, any era, any
turn (review 2026-11-01, mind_memory F2). A native played in a flash-forward
(ordinal +1) at turns 50-60 and back in the present at 61 took the
flash-forward's rows into a present-era tick: twelve memories of a future it
has not reached.
"""

from __future__ import annotations

import time

from core.frames import create_frame
from world import offscreen


def _setup(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("A", "", time.time()))
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,source,created) "
                         "VALUES(?,?,?,?)", ("Kestrel", "{}", "{}", time.time()))
    entry = {"id": "kestrel_uid", "char_id": char_id, "state": {},
             "sheet": {"identity": {"name": "Kestrel", "uid": "kestrel_uid"},
                       "psychology": {"drive": {"essence": "hold the gate"}}}}
    return cid, char_id, entry


def _remember(temp_db, cid, char_id, turn_idx, text, frame_id=None, archived=0):
    temp_db.qi("INSERT INTO memories(chat_id,char_id,turn_idx,content,frame_id,archived) "
               "VALUES(?,?,?,?,?,?)", (cid, char_id, turn_idx, text, frame_id, archived))


def test_a_present_tick_never_reads_a_flash_forward(temp_db):
    cid, char_id, entry = _setup(temp_db)
    ahead = create_frame(cid, label="a year on", ordinal=1, kind="future")
    _remember(temp_db, cid, char_id, 3, "the gate held through the storm")
    for t in range(50, 61):
        _remember(temp_db, cid, char_id, t, f"the gate fell to the river men ({t})", ahead)
    ctx = offscreen.agent_context(cid, entry, frame_id=None, turn_idx=62)
    assert [m["summary"] for m in ctx["memories"]] == ["the gate held through the storm"]


def test_a_tick_reads_nothing_past_its_own_turn(temp_db):
    """The turn the tick runs after is its last: a row stamped later is a
    rerun's outcome, never this mind's yet."""
    cid, char_id, entry = _setup(temp_db)
    _remember(temp_db, cid, char_id, 3, "the gate held")
    _remember(temp_db, cid, char_id, 5, "the gate was barred at dusk")
    _remember(temp_db, cid, char_id, 9, "a later turn's outcome")
    ctx = offscreen.agent_context(cid, entry, frame_id=None, turn_idx=5)
    assert [m["summary"] for m in ctx["memories"]] == [
        "the gate was barred at dusk", "the gate held"]


def test_newest_twelve_unarchived_rows_still_arrive(temp_db):
    cid, char_id, entry = _setup(temp_db)
    for t in range(1, 16):
        _remember(temp_db, cid, char_id, t, f"watch {t}")
    _remember(temp_db, cid, char_id, 16, "an archived aside", archived=1)
    ctx = offscreen.agent_context(cid, entry, frame_id=None, turn_idx=20)
    assert [m["turn_idx"] for m in ctx["memories"]] == list(range(15, 3, -1))
