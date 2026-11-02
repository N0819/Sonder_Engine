"""The plot-package store is one JSON row written back whole, and its writers
run on four threads: the Planner's reply, a fill or Dramaturge job, the
commit tail's clock pass and the panel. Audit 2026-11-01 (agents_narration_
planner F1): `fire_due_clocks` ran with no transaction, caught only
`ValueError` and saved the store once at the end, so an operation that landed
before a later one failed landed AGAIN on every following beat; and every
writer read the store outside its write, so a write that landed between
another writer's read and its save was erased by construction.
"""
from __future__ import annotations

import threading
import time

import pytest

from core import db as core_db
from story import plot_packages as pp
from story.plot_packages import (OPERATIONS, draft_operation, edit_package,
                                 fire_due_clocks, get_package, new_package,
                                 publish_package, validate_package)


def _body(name, place, post=""):
    return {"name": name, "place": place, "berth": place, "competence": {},
            "available": True, "home_post": post}


def _story(db, *, turns=3):
    from world.charter_runtime import save_registry
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Store", "A port at dusk.", time.time()))

    def room(name, *exits):
        return {"name": name, "desc": name + ".",
                "adjacent": [{"to": e, "barrier": "open_door"} for e in exits]}
    db.wset(cid, "scene", {"location": "Port", "rooms": {
        "quay": room("Quay", "hall"), "hall": room("Hall", "quay")},
        "positions": {"Wren": "quay"}, "entities": {}, "attire": {}})
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    save_registry(cid, {"items": {"hall": {"state": {
        "key": "hall", "priority": [], "clock_hours": 10.0,
        "upkeeps": {"court": {"place": "hall", "level": 0.9}},
        "posts": {"reeve": {"place": "hall", "serves": ["court"], "requires": {},
                            "reports_to": "reeve"}},
        "bodies": {"r1": _body("Halin Nook", "hall", "reeve"),
                   "w1": _body("Bran Gate", "quay")},
        "watch": {"reeve": "r1"},
        "economy": {"goods": {"grain": {"label": "grain"}},
                    "stocks": {"hall": {"grain": 10.0}}},
    }}}})
    ids = [db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                 "VALUES(?,?,?,?)", (cid, i, "", time.time()))
           for i in range(turns)]
    return cid, ids


def _grain(cid):
    from world.charter_runtime import registry_for
    return registry_for(cid)["items"]["hall"]["state"]["economy"]["stocks"]["hall"]["grain"]


def _publish(cid, uid):
    validate_package(cid, uid)
    return publish_package(cid, uid, expected_revision=get_package(cid, uid)["revision"])


def test_an_operation_that_landed_is_not_landed_again_when_a_later_one_fails(
        temp_db, monkeypatch):
    """The confirmed scenario: op A (stock arrives) lands, op B's seam raises
    something other than ValueError. The commit tail turns the raise into a
    warning; on the next beat A must not land a second time."""
    cid, turn_ids = _story(temp_db)
    pkg = new_package(cid, title="The grain boat", premise="p")
    edit_package(cid, pkg["uid"], {"clocks": [
        {"id": "clock_boat", "label": "the boat", "due_turns": 1}]})
    draft_operation(cid, pkg["uid"], {
        "op": "adjust_stock", "charter": "hall", "holder": "hall",
        "good": "grain", "delta": 5, "clock": "clock_boat"})
    draft_operation(cid, pkg["uid"], {
        "op": "arrival", "who": "hall/w1", "room": "hall", "clock": "clock_boat"})
    _publish(cid, pkg["uid"])
    assert _grain(cid) == 10.0

    def boom(*_a, **_k):
        raise KeyError("a charter surgery tripped over its own record")
    monkeypatch.setitem(OPERATIONS["arrival"], "apply", boom)

    for turn in (3, 4, 5):
        try:                    # what the commit tail does with a raise
            fire_due_clocks(cid, turn, turn_id=turn_ids[-1])
        except Exception:
            pass
    assert _grain(cid) == 15.0
    stored = get_package(cid, pkg["uid"])
    stock, arrival = stored["operations"]
    assert stock.get("applied") is not None
    assert arrival.get("applied") is None
    assert "KeyError" in arrival["refused"]["errors"][0]
    assert stored["clocks"][0]["fired_turn"] == 3
    assert any(h["action"] == "operation_refused"
               for h in stored["provenance"]["history"])


def test_a_clock_pass_does_not_erase_a_package_another_thread_wrote(temp_db):
    """The race: a Room thread writes package P2 inside its own transaction
    while the commit tail's clock pass reads and rewrites the store. The pass
    must read the store as it stands once the other write has landed."""
    cid, turn_ids = _story(temp_db)
    first = new_package(cid, title="The bells", premise="p")
    edit_package(cid, first["uid"], {"clocks": [
        {"id": "clock_b", "label": "bells", "due_turns": 1}]})
    draft_operation(cid, first["uid"], {
        "op": "scheduled_consequence", "clock": "clock_b", "summary": "bells"})
    _publish(cid, first["uid"])
    second = new_package(cid, title="The tower", premise="p")

    written, release = threading.Event(), threading.Event()

    def room_thread():
        with core_db.transaction():
            draft_operation(cid, second["uid"], {
                "op": "schedule_event", "summary": "a tower bell cracks",
                "due_in_turns": 2})
            written.set()
            release.wait(5)
        core_db.close_connection()

    worker = threading.Thread(target=room_thread)
    worker.start()
    assert written.wait(5)
    timer = threading.Timer(0.3, release.set)
    timer.start()
    fired = fire_due_clocks(cid, 3, turn_id=turn_ids[-1])
    worker.join(5)
    timer.cancel()
    assert fired["fired"] == [(first["uid"], "clock_b")]
    assert [op["op"] for op in get_package(cid, second["uid"])["operations"]] \
        == ["schedule_event"]
    assert get_package(cid, first["uid"])["clocks"][0]["fired_turn"] == 3


def test_two_drafting_writers_on_two_threads_both_land(temp_db):
    """The drafting writers race each other the same way: a fill job and the
    panel's reply each drafting into its own package."""
    cid, _ids = _story(temp_db)
    one = new_package(cid, title="One", premise="p")
    two = new_package(cid, title="Two", premise="p")
    written, release = threading.Event(), threading.Event()

    def fill_job():
        with core_db.transaction():
            draft_operation(cid, one["uid"], {
                "op": "schedule_event", "summary": "a gull screams",
                "due_in_turns": 1})
            written.set()
            release.wait(5)
        core_db.close_connection()

    worker = threading.Thread(target=fill_job)
    worker.start()
    assert written.wait(5)
    timer = threading.Timer(0.3, release.set)
    timer.start()
    draft_operation(cid, two["uid"], {
        "op": "schedule_event", "summary": "a bell answers", "due_in_turns": 1})
    worker.join(5)
    timer.cancel()
    assert len(get_package(cid, one["uid"])["operations"]) == 1
    assert len(get_package(cid, two["uid"])["operations"]) == 1


def test_a_publish_does_not_erase_a_package_another_thread_wrote(temp_db,
                                                                monkeypatch):
    """`publish_package` read the store before its transaction and wrote the
    whole store back inside it."""
    cid, _ids = _story(temp_db)
    pub = new_package(cid, title="Published", premise="p")
    draft_operation(cid, pub["uid"], {
        "op": "schedule_event", "summary": "the tide turns", "due_in_turns": 1})
    validate_package(cid, pub["uid"])
    other = new_package(cid, title="Other", premise="p")
    written, release = threading.Event(), threading.Event()

    def room_thread():
        with core_db.transaction():
            draft_operation(cid, other["uid"], {
                "op": "schedule_event", "summary": "a gull screams",
                "due_in_turns": 1})
            written.set()
            release.wait(5)
        core_db.close_connection()

    real_packages = pp.packages
    reads = []

    def watching_packages(*args, **kwargs):
        out = real_packages(*args, **kwargs)
        reads.append(out)
        if len(reads) == 1:
            # The publish has read the store; now the other writer lands.
            worker.start()
            assert written.wait(5)
            threading.Timer(0.3, release.set).start()
        return out

    worker = threading.Thread(target=room_thread)
    revision = get_package(cid, pub["uid"])["revision"]
    monkeypatch.setattr(pp, "packages", watching_packages)
    publish_package(cid, pub["uid"], expected_revision=revision)
    monkeypatch.setattr(pp, "packages", real_packages)
    worker.join(5)
    assert get_package(cid, pub["uid"])["status"] == "published"
    assert len(get_package(cid, other["uid"])["operations"]) == 1
