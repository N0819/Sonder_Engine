"""Review 2026-09-07 B6: one stored registry shape, written at one chokepoint.

The registry was stored in two shapes. `save_registry` reduced to the SPLIT
shape (a person once at registry level, an institution recording only who it
employs) while the two landing paths -- `land_presim`
(charter_runtime.py:1843 pre-fix) and `land_snapshot` (:2719 pre-fix) -- wrote
the JOINED working shape straight to the world row, so what was on disk
depended on which writer ran last. Every write now goes through
`_write_registry`, so the stored shape is the split one whoever wrote it.
"""

from __future__ import annotations

import copy
import time

from world.charter_runtime import (
    CHARTERS_KEY,
    flush_registry_session,
    land_presim,
    land_snapshot,
    normalize_registry,
    registry_session,
    save_registry,
)

from charter_fixtures import SHIP


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Registry shape", "", time.time()))


def _crewed():
    return normalize_registry(
        {"items": {"ship": {"state": copy.deepcopy(SHIP),
                            "last_elapsed_seconds": 0.0}}})


def _assert_split(stored, who):
    assert set(stored) == {"version", "items", "people"}, \
        f"{who} wrote a shape that is not the stored one"
    state = stored["items"]["ship"]["state"]
    assert "bodies" not in state, f"{who} stored people inside the institution"
    assert state["members"], f"{who} dropped the membership list"
    assert stored["people"], f"{who} stored no people at registry level"
    return stored


def test_every_registry_writer_lands_the_same_split_shape(temp_db):
    """Every registry writer agrees on what is on disk.

    Review 2026-09-07 B6: the four writers are `save_registry`, the deferred
    `flush_registry_session` a commit actually takes, and the two landing
    paths. Each is driven here; `tests/test_registry_session.py` pins only
    the write COUNT, so a flush that wrote a joined shape of its own would
    still be one write of one key and would pass everything else.
    """
    saved_cid = _chat(temp_db)
    save_registry(saved_cid, _crewed(), None)
    saved = _assert_split(temp_db.wget(saved_cid, CHARTERS_KEY, {}),
                          "save_registry")

    flushed_cid = _chat(temp_db)
    with registry_session():
        save_registry(flushed_cid, _crewed(), None)
        assert flush_registry_session() == 1
    flushed = _assert_split(temp_db.wget(flushed_cid, CHARTERS_KEY, {}),
                            "flush_registry_session")

    presim_cid = _chat(temp_db)
    land_presim(presim_cid, None, _crewed(), [], base_turn=1)
    presimmed = _assert_split(temp_db.wget(presim_cid, CHARTERS_KEY, {}),
                              "land_presim")

    snapshot_cid = _chat(temp_db)
    temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
               "VALUES(?,?,?,?,?)", (snapshot_cid, 1, "", time.time(), None))
    temp_db.wset(snapshot_cid, "offscreen_epoch", {"beat_id": "beat-1"})
    land_snapshot(snapshot_cid, None, 1, "beat-1", _crewed(), [], [])
    landed = _assert_split(temp_db.wget(snapshot_cid, CHARTERS_KEY, {}),
                           "land_snapshot")

    assert set(saved["people"]) == set(flushed["people"]) \
        == set(presimmed["people"]) == set(landed["people"])
    assert saved["items"]["ship"]["state"]["members"] \
        == flushed["items"]["ship"]["state"]["members"] \
        == presimmed["items"]["ship"]["state"]["members"] \
        == landed["items"]["ship"]["state"]["members"]
