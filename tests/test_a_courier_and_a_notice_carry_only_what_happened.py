"""Couriers and notices, held to the road and the wall they stand on (audit
2026-11-01, story_room_carriers F4, F7, F8, F11, F16, F19, F20, F21, E1).

* A courier crossing several edges in one sweep paid the FIRST edge's price
  for all of them: 1,845 s of road in 180 s.
* A refused send or post still filed an invented claim in the sender's own
  ledger, so a mind was told next beat that it had made up something it never
  said.
* A courier addressed to nobody the story holds waited at the gate forever.
* A torn-down carcass came back at the next charter landing, and carcasses
  were sent to the notice-wording model.
* The wording landing read and wrote the artifacts row with no transaction,
  erasing a bill a concurrent commit posted; a fenced answer was refused by a
  bare `json.loads`, and every beat while a bill was blank started a second
  job for it.
"""
from __future__ import annotations

import json
import threading
import time
import types

import pytest

from core import db as core_db


def _world(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Road story", "", time.time()))
    chars = {}
    for name in ("Mora", "Tavi"):
        sheet = json.dumps({"identity": {"name": name, "uid": name.lower()}})
        char_id = db.qi("INSERT INTO characters(name,sheet,source,created) "
                        "VALUES(?,?,?,?)", (name, sheet, "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
        chars[name] = char_id
    turn_id = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                    "VALUES(?,?,?,?)", (cid, 3, "", time.time()))
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    scene = {"rooms": {
        "square": {"name": "Square", "adjacent": [{"to": "road"}]},
        "road": {"name": "Road", "adjacent": [{"to": "square"}, {"to": "gate"}]},
        "gate": {"name": "Gate", "adjacent": [{"to": "road"}]}},
        "positions": {"Mora": "square", "Tavi": "square"}}
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(id=turn_id, idx=3, frame_id=None),
        director_resolve=None, director_establish=None)
    return cid, chars, scene, ctx


def _reports(db, cid, char_id):
    row = db.q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
               (cid, char_id), one=True)
    return json.loads(row["state"] or "{}").get("carried_reports") or []


# ---------------------------------------------------------------------------
# F11 -- each edge its own price
# ---------------------------------------------------------------------------

def test_a_courier_pays_each_edge_its_own_price(monkeypatch):
    from story import couriers
    prices = {("a", "b"): 45.0, ("b", "c"): 600.0, ("c", "d"): 600.0,
              ("d", "e"): 600.0}
    monkeypatch.setattr(couriers, "courier_edge_seconds",
                        lambda scene, here, nxt, flat: prices[(here, nxt)])
    rider = couriers.new_courier(
        1, origin="a", destination="e", route=["a", "b", "c", "d", "e"], turn=1,
        clock_seconds=0.0, description="a rider", report={"claim": "x"},
        sealed=False, pace="walking")
    neighbors = {"a": {"b"}, "b": {"c"}, "c": {"d"}, "d": {"e"}}
    (moved,), _moves = couriers.advance_couriers([rider], neighbors, 200.0,
                                                 scene={})
    assert moved["at"] == "b" and moved["moved_at"] == 45.0
    (later,), _moves = couriers.advance_couriers([moved], neighbors, 700.0,
                                                 scene={})
    assert later["at"] == "c" and later["moved_at"] == 645.0
    (arrived,), _moves = couriers.advance_couriers([later], neighbors, 1845.0,
                                                   scene={})
    assert arrived["at"] == "e" and arrived["status"] == "arrived"


# ---------------------------------------------------------------------------
# F8 -- a refused op files no invented claim
# ---------------------------------------------------------------------------

def test_a_refused_send_leaves_the_senders_ledger_as_it_was(temp_db):
    from story.couriers import run_couriers
    cid, chars, scene, ctx = _world(temp_db)
    scene["rooms"]["island"] = {"name": "Island", "adjacent": []}
    _metrics, rejected = run_couriers(ctx, scene, [
        {"op": "send", "sender": "Mora", "to_room": "island",
         "claim": "the miller cheats", "method": "letter"}])
    assert any("no passable route" in r for r in rejected), rejected
    assert _reports(temp_db, cid, chars["Mora"]) == []


def test_a_refused_post_leaves_the_posters_ledger_as_it_was(temp_db):
    from story.artifacts import ARTIFACTS_WORLD_KEY, new_artifact, run_artifacts
    cid, chars, scene, ctx = _world(temp_db)
    standing = new_artifact(cid, room="square", turn=3,
                            description="a wanted bill", report={}, posted_by="Tavi")
    temp_db.wset(cid, ARTIFACTS_WORLD_KEY, [standing])
    _metrics, rejected = run_artifacts(ctx, scene, [
        {"op": "post", "poster": "Mora", "claim": "Tavi stole the bell",
         "description": "a wanted bill"}])
    assert any("already on the wall" in r for r in rejected), rejected
    assert _reports(temp_db, cid, chars["Mora"]) == []


def test_a_landed_send_still_files_what_the_sender_made_up(temp_db):
    from story.couriers import run_couriers
    cid, chars, scene, ctx = _world(temp_db)
    metrics, rejected = run_couriers(ctx, scene, [
        {"op": "send", "sender": "Mora", "to_room": "gate",
         "claim": "the miller cheats", "method": "letter"}])
    assert metrics["dispatched"] == 1, rejected
    (own,) = _reports(temp_db, cid, chars["Mora"])
    assert own["provenance"] == "invented"


# ---------------------------------------------------------------------------
# F20 -- addressed to somebody the story holds
# ---------------------------------------------------------------------------

def test_a_courier_addressed_to_nobody_the_story_holds_is_refused(temp_db):
    from story.couriers import COURIERS_WORLD_KEY, run_couriers
    cid, chars, scene, ctx = _world(temp_db)
    metrics, rejected = run_couriers(ctx, scene, [
        {"op": "send", "sender": "Mora", "to_room": "gate", "addressee": "the Baron",
         "claim": "the miller cheats", "method": "letter"}])
    assert metrics["dispatched"] == 0
    assert any("the Baron" in r for r in rejected), rejected
    assert temp_db.wget(cid, COURIERS_WORLD_KEY, []) == []
    assert _reports(temp_db, cid, chars["Mora"]) == []


def test_a_waiting_courier_whose_addressee_is_gone_ends_his_route(temp_db):
    """Addressed to somebody the story no longer holds: there is nobody to
    wait for, and a slot on the road is held by nobody's errand."""
    from story.couriers import COURIERS_WORLD_KEY, new_courier, run_couriers
    cid, chars, scene, ctx = _world(temp_db)
    rider = new_courier(cid, origin="gate", destination="gate", route=["gate"],
                        turn=1, clock_seconds=0.0, description="a rider",
                        report={"world_event_id": "claim:z", "claim": "come",
                                "retellings": 0}, sealed=True, pace="riding")
    rider["addressee"] = "Somebody Gone"
    temp_db.wset(cid, COURIERS_WORLD_KEY, [rider])
    metrics, rejected = run_couriers(ctx, scene, [])
    stored = temp_db.wget(cid, COURIERS_WORLD_KEY, [])
    assert stored[0]["status"] not in ("arrived", "en_route"), stored
    assert metrics["couriers_standing"] == 0
    assert any("Somebody Gone" in r for r in rejected), rejected


# ---------------------------------------------------------------------------
# F7, F16, F19 -- a carcass is not a bill
# ---------------------------------------------------------------------------

def _registry_with_spoor():
    return {"items": {"wolf": {"state": {"spoor": [
        {"key": "spoor:deer:1", "place": "square", "description": "a torn deer",
         "kind": "carcass", "at_hours": 52.5}]}}}}


def test_a_carcass_torn_down_stays_down(temp_db):
    from story.artifacts import (ARTIFACTS_WORLD_KEY, post_spoor, run_artifacts)
    cid, chars, scene, ctx = _world(temp_db)
    post_spoor(cid, _registry_with_spoor(), 3)
    (carcass,) = temp_db.wget(cid, ARTIFACTS_WORLD_KEY, [])
    run_artifacts(ctx, scene, [{"op": "remove", "by": "Mora",
                                "artifact_id": carcass["uid"]}])
    post_spoor(cid, _registry_with_spoor(), 4)
    rows = temp_db.wget(cid, ARTIFACTS_WORLD_KEY, [])
    assert [(a["uid"], a["status"]) for a in rows] == [(carcass["uid"], "removed")]


def test_a_carcass_is_never_sent_for_wording(temp_db):
    from story import artifacts
    cid, chars, scene, ctx = _world(temp_db)
    artifacts.post_spoor(cid, _registry_with_spoor(), 3)
    submitted = []
    from core import jobs
    original = jobs.submit
    jobs.submit = lambda *a, **k: submitted.append(a) or None
    try:
        assert artifacts.schedule_artifact_wording(ctx) is None
    finally:
        jobs.submit = original
    assert submitted == []


def test_standing_carcasses_do_not_take_the_notice_slots(temp_db):
    from story.artifacts import (ARTIFACTS_WORLD_KEY, MAX_ARTIFACTS, post_spoor,
                                 run_artifacts)
    cid, chars, scene, ctx = _world(temp_db)
    many = {"items": {"wolf": {"state": {"spoor": [
        {"key": "spoor:%d" % i, "place": "square", "description": "a carcass %d" % i}
        for i in range(MAX_ARTIFACTS)]}}}}
    post_spoor(cid, many, 3)
    metrics, rejected = run_artifacts(ctx, scene, [
        {"op": "post", "poster": "Mora", "claim": "the well is fouled",
         "description": "a warning chalked on the wall"}])
    assert metrics["artifacts_posted"] == 1, rejected


# ---------------------------------------------------------------------------
# F4 (lane F3), F21 -- the wording landing
# ---------------------------------------------------------------------------

def test_a_wording_landing_keeps_a_bill_a_concurrent_commit_posted(temp_db):
    from story import artifacts as A
    cid, chars, scene, ctx = _world(temp_db)
    first = {"uid": "artifact:a1", "room": "square", "status": "posted",
             "posted_turn": 1, "text": "", "wording_failures": 0,
             "report": {"claim": "x"}}
    temp_db.wset(cid, A.ARTIFACTS_WORLD_KEY, [first])
    posted, release = threading.Event(), threading.Event()

    def turn_commit():
        with core_db.transaction():
            current = core_db.wget(cid, A.ARTIFACTS_WORLD_KEY, [])
            core_db.wset(cid, A.ARTIFACTS_WORLD_KEY, current + [{
                "uid": "artifact:c1", "room": "square", "status": "posted",
                "posted_turn": 6, "text": "", "report": {"claim": "y"}}])
            posted.set()
            release.wait(5)
        core_db.close_connection()

    worker = threading.Thread(target=turn_commit)
    worker.start()
    assert posted.wait(5)
    threading.Timer(0.3, release.set).start()
    record = A.land_artifact_wording(cid, "artifact:a1", "HEAR YE", "",
                                     base_turn=5)
    worker.join(5)
    assert record["landed"]
    rows = {a["uid"]: a for a in temp_db.wget(cid, A.ARTIFACTS_WORLD_KEY, [])}
    assert set(rows) == {"artifact:a1", "artifact:c1"}
    assert rows["artifact:a1"]["text"] == "HEAR YE"


def test_a_fenced_wording_answer_is_read(monkeypatch):
    from llm import providers
    from story import artifacts as A
    monkeypatch.setattr(providers, "chat_complete",
                        lambda *a, **k: '```json\n{"text": "HEAR YE: the well is fouled"}\n```')
    text, error = A.mint_wording(
        {"description": "a notice", "report": {"claim": "the well is fouled"}}, [])
    assert error == "" and text == "HEAR YE: the well is fouled"


def test_a_blank_bill_is_worded_by_one_job_however_many_beats_ask(temp_db, monkeypatch):
    from story import artifacts as A
    from core import jobs
    cid, chars, scene, ctx = _world(temp_db)
    temp_db.wset(cid, A.ARTIFACTS_WORLD_KEY, [{
        "uid": "artifact:a1", "room": "square", "status": "posted",
        "posted_turn": 1, "text": "", "wording_failures": 0,
        "report": {"claim": "x"}}])
    keys = []
    monkeypatch.setattr(jobs, "submit",
                        lambda chat, key, fn, base_turn=None: keys.append(key))
    A.schedule_artifact_wording(ctx)
    ctx.turn.idx = 4
    A.schedule_artifact_wording(ctx)
    assert len(keys) == 2 and keys[0] == keys[1]


# ---------------------------------------------------------------------------
# E1 -- a quiet beat builds no carrier index
# ---------------------------------------------------------------------------

def test_a_beat_with_nothing_on_the_road_or_the_wall_builds_no_index(temp_db,
                                                                     monkeypatch):
    from story import artifacts, carriers, couriers
    cid, chars, scene, ctx = _world(temp_db)
    built = []
    real = carriers._build_carriers

    def counting(*a, **k):
        built.append(1)
        return real(*a, **k)
    monkeypatch.setattr(carriers, "_build_carriers", counting)
    couriers.run_couriers(ctx, scene, [])
    artifacts.run_artifacts(ctx, scene, [])
    assert built == []


def test_a_wording_answer_that_is_no_json_is_a_failure_not_the_bills_words(
        monkeypatch):
    """The reader's fallback files prose under `text` -- the bill's own key --
    so it is asked to refuse instead: a model's preamble is never a notice."""
    from llm import providers
    from story import artifacts as A
    monkeypatch.setattr(providers, "chat_complete",
                        lambda *a, **k: "Sure! Here is the notice you asked for.")
    text, error = A.mint_wording(
        {"description": "a notice", "report": {"claim": "the well is fouled"}}, [])
    assert text == "" and error
