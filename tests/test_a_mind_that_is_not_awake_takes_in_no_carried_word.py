"""The carrier network's channels close on a mind that is not awake, and a
newcomer meets what still stands as what stands (audit 2026-11-01,
story_room_carriers F2, F3).

THE ENGINE ALREADY HAS THE RULE. Perception excludes an asleep, sedated or
unconscious mind from its call (`story.scene.NON_AWAKE_GATED`, read through
`awareness_map` with this beat's own state_diff laid over it); the carriers did
not ask. So an unconscious body in the square acquired an accusation spoken
while she was out and woke an eyewitness to it, a telling to a sleeper copied
the report into him, a courier handed a letter to a sleeping addressee and a
sedated reader read a bill.

AND A SURFACE MET LATER IS NOT AN EYEWITNESS ACCOUNT. The arrival window files
what a body walking in meets of what landed there earlier; it was filed as
`witnessed_surface`, retellings 0 -- the record of a body that saw it happen --
so a man who walked into an empty chapel six hours after an accusation held an
eyewitness account of it.
"""
from __future__ import annotations

import json
import time
import types

import pytest


class _Chat(dict):
    @property
    def id(self):
        return self["id"]


def _world(db, *, asleep=(), resolved=None):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Carrier story", "", time.time()))
    chars = {}
    for name in ("Mora", "Tavi", "Hal"):
        sheet = json.dumps({"identity": {"name": name, "uid": name.lower()}})
        char_id = db.qi("INSERT INTO characters(name,sheet,source,created) "
                        "VALUES(?,?,?,?)", (name, sheet, "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
        chars[name] = char_id
    turn_id = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                    "VALUES(?,?,?,?)", (cid, 3, "", time.time()))
    for i, name in enumerate(asleep):
        db.qi("INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
              "started_at,payload,active) VALUES(?,?,?,?,?,?,1)",
              ("knocked_out_%d" % i, cid, name, "awareness", 10.0,
               json.dumps({"subject_id": name, "kind": "awareness",
                           "state": {"level": "unconscious",
                                     "cause": "a blow"}})))
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 100.0})
    scene = {"rooms": {"square": {"name": "Square", "adjacent": ["road"]},
                       "road": {"name": "Road", "adjacent": ["square"]}},
             "positions": {"Mora": "square", "Tavi": "square", "Hal": "road"}}
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(id=turn_id, idx=3, frame_id=None),
        director_resolve=resolved, director_establish=None,
        warnings=[])
    ctx.add_warning = ctx.warnings.append
    return cid, chars, scene, ctx, turn_id


def _event(db, cid, turn_id, event_id, *, room="square", occurred=50.0,
           witnessed="the reeve accused the miller aloud", stands=None):
    payload = {"what": "an accusation", "witnessed": witnessed}
    if stands is not None:
        payload["stands"] = stands
    db.qi("INSERT INTO world_events(event_id,chat_id,turn_id,frame_id,"
          "occurred_at,duration_seconds,kind,location_id,payload,seed,committed) "
          "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          (event_id, cid, turn_id, None, occurred, 0.0, "consequence", room,
           json.dumps(payload), "seed", time.time()))


def _reports(db, cid, char_id):
    row = db.q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
               (cid, char_id), one=True)
    return json.loads(row["state"] or "{}").get("carried_reports") or []


# ---------------------------------------------------------------------------
# F2 -- the channels close on a mind that is not awake
# ---------------------------------------------------------------------------

def test_an_unconscious_body_acquires_nothing_where_a_surface_lands(temp_db):
    from story.carriers import advance_carriers
    cid, chars, scene, ctx, turn_id = _world(temp_db, asleep=("Mora",))
    _event(temp_db, cid, turn_id, "accusation_1")
    advance_carriers(ctx, scene, {"events": [{"event_id": "accusation_1"}]})
    assert _reports(temp_db, cid, chars["Mora"]) == []
    assert [r["world_event_id"] for r in _reports(temp_db, cid, chars["Tavi"])] \
        == ["accusation_1"]


def test_a_knockout_resolved_this_beat_closes_the_channel_this_beat(temp_db):
    """The beat's own state_diff is laid over the committed conditions, as
    perception reads it: a body knocked out by this beat learns nothing of it."""
    from story.carriers import advance_carriers
    resolved = {"state_diff": {"conditions": {"ko": [{
        "condition_id": "ko", "subject_id": "Tavi", "kind": "awareness",
        "state": {"level": "unconscious"}, "active": 1}]}}}
    cid, chars, scene, ctx, turn_id = _world(temp_db, resolved=resolved)
    _event(temp_db, cid, turn_id, "accusation_1")
    advance_carriers(ctx, scene, {"events": [{"event_id": "accusation_1"}]})
    assert _reports(temp_db, cid, chars["Tavi"]) == []
    assert len(_reports(temp_db, cid, chars["Mora"])) == 1


def test_a_telling_to_a_sleeper_or_from_one_is_refused(temp_db):
    from story.carriers import apply_tellings
    resolved = {"dialogue_log": [{"speaker": "Tavi", "text": "Listen."},
                                 {"speaker": "Mora", "text": "..."}]}
    cid, chars, scene, ctx, turn_id = _world(temp_db, asleep=("Mora",),
                                             resolved=resolved)
    temp_db.qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
               (json.dumps({"carried_reports": [{
                   "world_event_id": "accusation_1", "claim": "the reeve "
                   "accused the miller aloud", "kind": "consequence",
                   "occurred_at": 50.0, "retellings": 0, "told_by": "",
                   "provenance": "witnessed_surface"}]}), cid, chars["Tavi"]))
    applied, rejected = apply_tellings(ctx, scene, [
        {"speaker": "Tavi", "listener": "Mora", "world_event_id": "accusation_1"}])
    assert applied == 0
    assert any("unconscious" in r for r in rejected), rejected
    assert _reports(temp_db, cid, chars["Mora"]) == []


def test_a_sleeper_reads_no_bill_and_is_handed_no_letter(temp_db):
    from story.artifacts import (ARTIFACTS_WORLD_KEY, new_artifact,
                                 run_artifacts)
    from story.couriers import COURIERS_WORLD_KEY, new_courier, run_couriers
    cid, chars, scene, ctx, turn_id = _world(temp_db, asleep=("Mora",))
    bill = new_artifact(cid, room="square", turn=1, description="a wanted bill",
                        report={"world_event_id": "claim:x", "claim": "Tavi stole",
                                "retellings": 0}, posted_by="")
    temp_db.wset(cid, ARTIFACTS_WORLD_KEY, [bill])
    metrics, rejected = run_artifacts(ctx, scene, [
        {"op": "read", "reader": "Mora", "artifact_id": bill["uid"]}])
    assert metrics["artifacts_read"] == 0
    assert any("unconscious" in r for r in rejected), rejected
    assert _reports(temp_db, cid, chars["Mora"]) == []

    rider = new_courier(cid, origin="square", destination="square",
                        route=["square"], turn=1, clock_seconds=0.0,
                        description="a rider", sealed=True, pace="riding",
                        report={"world_event_id": "claim:y",
                                "claim": "come home", "retellings": 0})
    rider["addressee"] = "Mora"
    temp_db.wset(cid, COURIERS_WORLD_KEY, [rider])
    metrics, _rejected = run_couriers(ctx, scene, [])
    assert metrics["courier_delivered"] == 0
    assert _reports(temp_db, cid, chars["Mora"]) == []
    standing = temp_db.wget(cid, COURIERS_WORLD_KEY, [])
    assert standing[0]["status"] == "arrived"     # he waits for her to wake


# ---------------------------------------------------------------------------
# F3 -- what a newcomer meets is filed as met, not as seen happen
# ---------------------------------------------------------------------------

def test_a_newcomer_files_a_standing_surface_as_standing_not_as_an_eyewitness(temp_db):
    from story.carriers import advance_carriers
    cid, chars, scene, ctx, turn_id = _world(temp_db)
    # Landed on an earlier beat, in the road, with nobody there.
    _event(temp_db, cid, turn_id, "gate_barred", room="road",
           witnessed="the toll gate stands barred")
    advance_carriers(ctx, scene, {"events": []})
    (met,) = _reports(temp_db, cid, chars["Hal"])
    assert met["world_event_id"] == "gate_barred"
    assert met["provenance"] == "standing_surface"
    assert met["provenance"] != "witnessed_surface"


def test_a_body_present_on_the_beat_is_still_the_eyewitness(temp_db):
    from story.carriers import advance_carriers
    cid, chars, scene, ctx, turn_id = _world(temp_db)
    _event(temp_db, cid, turn_id, "gate_barred", room="road",
           witnessed="the toll gate stands barred")
    advance_carriers(ctx, scene, {"events": [{"event_id": "gate_barred"}]})
    (seen,) = _reports(temp_db, cid, chars["Hal"])
    assert seen["provenance"] == "witnessed_surface"


def test_a_surface_its_producer_says_does_not_stand_is_not_offered_to_a_newcomer(temp_db):
    """The producer half (requested of the charter's owner) marks a surface
    that PASSES -- an act, not a state -- and the arrival window offers only
    what stands."""
    from story.carriers import advance_carriers
    cid, chars, scene, ctx, turn_id = _world(temp_db)
    _event(temp_db, cid, turn_id, "accusation_2", room="road", stands=False)
    _event(temp_db, cid, turn_id, "gate_barred", room="road", stands=True,
           witnessed="the toll gate stands barred")
    advance_carriers(ctx, scene, {"events": []})
    assert [r["world_event_id"] for r in _reports(temp_db, cid, chars["Hal"])] \
        == ["gate_barred"]


# ---------------------------------------------------------------------------
# The op shapes: a validated model or a plain dict
# ---------------------------------------------------------------------------

def test_carrier_ops_read_a_validated_model_as_its_fields(temp_db):
    from llm.schemas import ArtifactOp, CourierOp, TellingOp
    from story.carriers import plain_ops
    ops = plain_ops([TellingOp(speaker="Tavi", listener="Mora",
                               world_event_id="e1"),
                     {"speaker": "Hal"}, CourierOp(op="question", courier_id="c"),
                     ArtifactOp(op="read", reader="Mora", artifact_id="a"), 3])
    assert [type(o) for o in ops[:4]] == [dict] * 4
    assert ops[0]["listener"] == "Mora" and ops[2]["op"] == "question"
    # Anything else is passed on as it came, for the caller to refuse by name
    # ("courier op was not an object"), exactly as before.
    assert ops[4] == 3


def test_each_crowd_files_what_it_met_on_its_own_row(temp_db):
    """Two crowds, a surface standing in the second one's room: the second
    holds it as met standing, the first is untouched and stays itself (the
    crowd loop's own index must not be confused with the surface's)."""
    from story.carriers import advance_carriers
    from world import crowds
    cid, chars, scene, ctx, turn_id = _world(temp_db)
    _event(temp_db, cid, turn_id, "gate_barred", room="road",
           witnessed="the toll gate stands barred")
    square = crowds.new_crowd(cid, "square", band="a throng",
                              composition="market traders", since_turn=1)
    road = crowds.new_crowd(cid, "road", band="a knot of people",
                            composition="carters", since_turn=1)
    temp_db.wset(cid, crowds.CROWDS_WORLD_KEY, [square, road])
    advance_carriers(ctx, scene, {"events": []})
    stored = temp_db.wget(cid, crowds.CROWDS_WORLD_KEY, [])
    assert [c["uid"] for c in stored] == [square["uid"], road["uid"]]
    assert crowds.crowd_hearsay(stored[0]) == []
    (met,) = crowds.crowd_hearsay(stored[1])
    assert met["world_event_id"] == "gate_barred"
    assert met["provenance"] == "standing_surface"
