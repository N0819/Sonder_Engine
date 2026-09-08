"""The room registry is parsed ONCE per read, and the memo is never stale.

Review item C16 (2026-09-07): every `planned_*` reader ran its own
``SELECT ... FROM room_registry WHERE chat_id=? AND retired_turn_id IS NULL``
and re-parsed every row's payload JSON. Measured with
`tools/bench/room_registry_scan.py` on chat 114's 51-room plan: 19 scans a
turn -- 22.3 ms on the sanitized copy, 18.4 ms on a writable extract of the
same rows -- with nothing changed between the first scan and the nineteenth.
After: one scan and 8.1 ms. `structure.registry_rows` parses once and every
reader derives from it.

A memo is only worth having if its INVALIDATION is right, so that is what
these tests are: the scans collapse, and every way the registry can change
under a cached reader is still seen.
"""

from __future__ import annotations

import json
import threading
import time

from world import structure
from world.structure import (
    _planned_specs, planned_room_ids, planned_room_index, planned_topology,
    prepare_frontier_expansion, registry_rows)


def _chat(temp_db, name="Registry"):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      (name, "", time.time()))


def _plant(temp_db, cid, uid, name, planned, aliases=()):
    temp_db.qi(
        "INSERT INTO room_registry(chat_id,room_uid,name,aliases,payload) "
        "VALUES(?,?,?,?,?)",
        (cid, uid, name, json.dumps(list(aliases)),
         json.dumps({"planned": planned})))


def _count_scans(temp_db, monkeypatch, work):
    """How many `room_registry` SELECTs `work` issues."""
    from core import db

    scans = []
    real_q = db.q

    def counting_q(sql, args=(), one=False):
        if "room_registry" in sql:
            scans.append(sql)
        return real_q(sql, args, one=one)

    monkeypatch.setattr(db, "q", counting_q)
    try:
        result = work()
    finally:
        monkeypatch.setattr(db, "q", real_q)
    return result, len(scans)


# -- 1. one parse serves every reader -----------------------------------------

def test_a_turns_planned_readers_scan_the_registry_once(temp_db, monkeypatch):
    """The saving C16 was filed for: 19 scans a turn became one."""
    cid = _chat(temp_db)
    _plant(temp_db, cid, "square", "Market Square",
           {"structure": "town", "purpose": "market",
            "adjacent": [{"to": "lane"}]})
    _plant(temp_db, cid, "lane", "Slate Lane",
           {"structure": "town", "purpose": "dwelling",
            "adjacent": [{"to": "square"}]})
    scene = {"rooms": {}, "positions": {}}

    def work():
        return (sorted(planned_room_ids(cid)),
                planned_topology(cid),
                planned_room_index(cid, scene),
                structure.planned_room_spellings(cid),
                structure.planned_rooms_named_in(cid, "the market square"),
                structure.skeleton_rooms(cid, "town"),
                structure.planned_context(cid, "Slate Lane"))

    answers, scans = _count_scans(temp_db, monkeypatch, work)
    assert scans == 1
    assert answers[0] == ["lane", "square"]
    assert answers[6]["room_uid"] == "lane"


def test_the_shared_parse_is_one_object_per_read(temp_db):
    cid = _chat(temp_db)
    _plant(temp_db, cid, "square", "Market Square", {"structure": "town"})
    assert registry_rows(cid) is registry_rows(cid)


# -- 2. every way the registry changes is seen --------------------------------

def test_a_new_planned_room_is_seen_by_the_next_reader(temp_db):
    cid = _chat(temp_db)
    _plant(temp_db, cid, "square", "Market Square", {"structure": "town"})
    assert sorted(planned_room_ids(cid)) == ["square"]
    _plant(temp_db, cid, "lane", "Slate Lane", {"structure": "town"})
    assert sorted(planned_room_ids(cid)) == ["lane", "square"]


def test_a_renamed_room_is_seen_by_the_next_reader(temp_db):
    cid = _chat(temp_db)
    _plant(temp_db, cid, "square", "Market Square", {"structure": "town"})
    assert _planned_specs(cid)["square"][0] == "Market Square"
    temp_db.qi("UPDATE room_registry SET name=? WHERE chat_id=? AND "
               "room_uid=?", ("Reeve's Square", cid, "square"))
    assert _planned_specs(cid)["square"][0] == "Reeve's Square"


def test_a_retired_room_leaves_the_snapshot(temp_db):
    cid = _chat(temp_db)
    _plant(temp_db, cid, "square", "Market Square", {"structure": "town"})
    assert "square" in registry_rows(cid)
    turn = temp_db.qi("INSERT INTO turns(chat_id,idx,created) VALUES(?,?,?)",
                      (cid, 0, time.time()))
    temp_db.qi("UPDATE room_registry SET retired_turn_id=? WHERE chat_id=? "
               "AND room_uid=?", (turn, cid, "square"))
    assert "square" not in registry_rows(cid)


def test_a_write_inside_a_transaction_is_seen_after_it_commits(temp_db):
    cid = _chat(temp_db)
    _plant(temp_db, cid, "square", "Market Square", {"structure": "town"})
    assert sorted(planned_room_ids(cid)) == ["square"]
    with temp_db.transaction():
        temp_db.qtx(
            "INSERT INTO room_registry(chat_id,room_uid,name,aliases,payload) "
            "VALUES(?,?,?,?,?)",
            (cid, "lane", "Slate Lane", "[]",
             json.dumps({"planned": {"structure": "town"}})))
    assert sorted(planned_room_ids(cid)) == ["lane", "square"]


def test_another_threads_write_is_seen(temp_db):
    """`PRAGMA data_version` is the half of the token this needs: the web
    routes write `room_registry` on their own connection while a turn holds a
    parse on the pipeline's."""
    cid = _chat(temp_db)
    _plant(temp_db, cid, "square", "Market Square", {"structure": "town"})
    assert sorted(planned_room_ids(cid)) == ["square"]

    def writer():
        _plant(temp_db, cid, "lane", "Slate Lane", {"structure": "town"})

    thread = threading.Thread(target=writer)
    thread.start()
    thread.join()
    assert sorted(planned_room_ids(cid)) == ["lane", "square"]


def test_a_second_chat_gets_its_own_rows(temp_db):
    """The memo holds one story at a time; it must never answer for another."""
    first, second = _chat(temp_db, "One"), _chat(temp_db, "Two")
    _plant(temp_db, first, "square", "Market Square", {"structure": "town"})
    _plant(temp_db, second, "cell", "Cell", {"structure": "keep"})
    for _ in range(3):
        assert sorted(planned_room_ids(first)) == ["square"]
        assert sorted(planned_room_ids(second)) == ["cell"]


# -- 3. the one mutating reader does not poison the shared parse --------------

def test_frontier_expansion_does_not_edit_what_other_readers_hold(temp_db):
    """`prepare_frontier_expansion` appends to a spec's `adjacent` in place.
    Off the shared snapshot that edge would land in every later reader's view
    of the plan for the rest of the turn, and be written back by a commit that
    never minted it."""
    cid = _chat(temp_db)
    _plant(temp_db, cid, "gate", "Upland Gate",
           {"structure": "town", "purpose": "gatehouse", "adjacent": [],
            "frontier": ["upland road"]})
    before = json.dumps(planned_topology(cid), sort_keys=True)

    scene = {"rooms": {"gate": {"name": "Upland Gate", "adjacent": []}},
             "positions": {"Player": "gate"}}
    _scene, mutations = prepare_frontier_expansion(cid, scene)
    assert mutations, "the axis should have minted a stub"

    assert json.dumps(planned_topology(cid), sort_keys=True) == before
    assert _planned_specs(cid)["gate"][1]["frontier"] == ["upland road"]
