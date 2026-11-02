"""Every report a carrier writes says what KIND of teller it has -- a person,
a crowd, a courier, a notice -- because the writer knows and nothing
downstream can tell from the string (story_room_carriers F10; the reader half,
`agents.character.tellers_as_known`, relabels only a person and asked the
writers for the kind -- L6's request, 2026-11-01).

Before it, a rider's or a crowd's `told` copy carried only `told_by: "a
rider"` / `"talk among the market traders"`, and the floor -- which recognises
no such source, none being a body -- renamed it "the unfamiliar person".
"""
from __future__ import annotations

import json
import time
import types


def _world(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Kinds", "", time.time()))
    chars = {}
    for name in ("Mora", "Tavi"):
        sheet = json.dumps({"identity": {"name": name, "uid": name.lower()}})
        char_id = db.qi("INSERT INTO characters(name,sheet,source,created) "
                        "VALUES(?,?,?,?)", (name, sheet, "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
        chars[name] = char_id
    db.qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
          (json.dumps({"carried_reports": [{
              "world_event_id": "event:bell", "claim": "the bell rang twice",
              "kind": "consequence", "occurred_at": 1.0, "retellings": 0,
              "told_by": "", "provenance": "witnessed_surface"}]}),
           cid, chars["Tavi"]))
    turn_id = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                    "VALUES(?,?,?,?)", (cid, 3, "", time.time()))
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    scene = {"rooms": {"square": {"name": "Square", "adjacent": []}},
             "positions": {"Mora": "square", "Tavi": "square"}}
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(id=turn_id, idx=3, frame_id=None),
        director_resolve={"dialogue_log": [{"speaker": "Tavi", "text": "Hear."}]},
        director_establish=None)
    return cid, chars, scene, ctx


def _reports(db, cid, char_id):
    row = db.q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
               (cid, char_id), one=True)
    return json.loads(row["state"] or "{}").get("carried_reports") or []


def test_a_person_a_courier_and_a_notice_each_say_what_told(temp_db):
    from story.artifacts import ARTIFACTS_WORLD_KEY, new_artifact, run_artifacts
    from story.carriers import apply_tellings, reports_for_state
    from story.couriers import COURIERS_WORLD_KEY, new_courier, run_couriers
    cid, chars, scene, ctx = _world(temp_db)

    applied, rejected = apply_tellings(ctx, scene, [
        {"speaker": "Tavi", "listener": "Mora", "world_event_id": "event:bell"}])
    assert applied == 1, rejected
    (told,) = _reports(temp_db, cid, chars["Mora"])
    assert told["told_by"] == "Tavi" and told["told_by_kind"] == "person"

    rider = new_courier(cid, origin="square", destination="square",
                        route=["square"], turn=1, clock_seconds=0.0,
                        description="a rider", sealed=False, pace="riding",
                        report={"world_event_id": "event:fire",
                                "claim": "the mill burns", "retellings": 0})
    rider["addressee"] = "Mora"
    temp_db.wset(cid, COURIERS_WORLD_KEY, [rider])
    run_couriers(ctx, scene, [])
    delivered = [r for r in _reports(temp_db, cid, chars["Mora"])
                 if r["world_event_id"] == "event:fire"]
    assert delivered and delivered[0]["told_by_kind"] == "courier"

    bill = new_artifact(cid, room="square", turn=1, description="a wanted bill",
                        report={"world_event_id": "claim:x",
                                "claim": "Tavi stole the bell", "retellings": 0},
                        posted_by="")
    temp_db.wset(cid, ARTIFACTS_WORLD_KEY, [bill])
    run_artifacts(ctx, scene, [{"op": "read", "reader": "Mora",
                                "artifact_id": bill["uid"]}])
    read = [r for r in _reports(temp_db, cid, chars["Mora"])
            if r["world_event_id"] == "claim:x"]
    assert read and read[0]["told_by_kind"] == "artifact"

    # And the mind's projection carries it to the floor that reads it.
    projected = reports_for_state({"carried_reports": _reports(
        temp_db, cid, chars["Mora"])})
    assert {r["told_by_kind"] for r in projected} == {"person", "courier",
                                                      "artifact"}


def test_a_crowd_that_tells_says_it_is_a_crowd(temp_db):
    from story.carriers import apply_tellings
    from world import crowds
    cid, chars, scene, ctx = _world(temp_db)
    crowd = crowds.new_crowd(cid, "square", band="a throng",
                             composition="market traders", since_turn=1)
    crowd = crowds.add_hearsay(crowd, {
        "world_event_id": "event:grain", "claim": "the grain is short",
        "kind": "consequence", "occurred_at": 1.0, "retellings": 0})
    temp_db.wset(cid, crowds.CROWDS_WORLD_KEY, [crowd])
    applied, rejected = apply_tellings(ctx, scene, [
        {"speaker": crowd["uid"], "listener": "Mora",
         "world_event_id": "event:grain"}])
    assert applied == 1, rejected
    (heard,) = _reports(temp_db, cid, chars["Mora"])
    assert heard["told_by_kind"] == "crowd"
