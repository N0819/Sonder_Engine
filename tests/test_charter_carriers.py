"""Charter people are ordinary physical information carriers."""

from __future__ import annotations

import json
import time
import types


def _world(db):
    from world.charter import normalize_charter
    from world.charter_runtime import save_registry

    cid = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Charter carriers", "", time.time()))
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 4, "", time.time()))
    state = normalize_charter({
        "key": "market",
        "bodies": {
            "mara": {"name": "Mara Venn", "place": "square"},
            "orin": {"name": "Orin Pell", "place": "road"},
        },
    })
    save_registry(cid, {"market": state})
    scene = {
        "rooms": {
            "square": {"name": "Square", "adjacent": [
                {"to": "road", "barrier": "open"}]},
            "road": {"name": "Road", "adjacent": [
                {"to": "square", "barrier": "open"}]},
        },
        "positions": {},
    }
    db.qi(
        "INSERT INTO world_events(event_id,chat_id,turn_id,frame_id,"
        "occurred_at,duration_seconds,kind,location_id,payload,seed,committed) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("world_gate", cid, turn_id, None, 60.0, 0.0, "consequence", "square",
         json.dumps({"witnessed": "the north gate was chained shut",
                     "what": "a secret mechanism engaged"}),
         "seed", time.time()))
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(id=turn_id, idx=4, frame_id=None),
        director_resolve={"dialogue_log": []}, director_establish=None,
    )
    return cid, scene, ctx


def _minds(cid):
    from world.charter_runtime import registry_for

    return registry_for(cid)["items"]["market"]["state"]["minds"]


def test_only_the_colocated_charter_person_witnesses_a_public_surface(temp_db):
    from story.carriers import advance_carriers

    cid, scene, ctx = _world(temp_db)
    result = advance_carriers(
        ctx, scene, {"events": [{"event_id": "world_gate"}]})

    minds = _minds(cid)
    assert result["acquired"] == 1
    assert list(minds["mara"].values())[0]["claim_text"] == \
        "the north gate was chained shut"
    assert "secret mechanism" not in json.dumps(minds)
    assert not minds.get("orin")


def test_charter_carrier_projection_is_body_private_and_director_addressable(
        temp_db):
    from story.carriers import advance_carriers, carried_reports_view

    cid, scene, ctx = _world(temp_db)
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_gate"}]})

    view = carried_reports_view(cid, None, scene, chat=ctx.chat)
    assert view == [{
        "who": "Mara Venn", "world_event_id": "world_gate",
        "gist": "the north gate was chained shut", "retellings": 0,
    }]


def test_on_page_telling_moves_a_charter_rumour_without_proximity_broadcast(
        temp_db):
    from story.carriers import advance_carriers, apply_tellings
    from world.charter_runtime import registry_for, save_registry

    cid, scene, ctx = _world(temp_db)
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_gate"}]})
    registry = registry_for(cid)
    registry["items"]["market"]["state"]["bodies"]["orin"]["place"] = "square"
    save_registry(cid, registry)
    ctx.director_resolve = {
        "dialogue_log": [{"speaker": "Mara Venn", "quote":
                          "The north gate is chained shut."}]}

    applied, rejected = apply_tellings(ctx, scene, [{
        "speaker": "Mara Venn", "listener": "Orin Pell",
        "world_event_id": "world_gate",
    }])

    claim = next(iter(_minds(cid)["orin"].values()))
    assert (applied, rejected) == (1, [])
    assert claim["heard_from"] == "Mara Venn"
    assert claim["claim_text"] == "the north gate was chained shut"
    assert claim["retellings"] == 1


def test_charter_report_survives_promotion_with_wording_and_provenance(temp_db):
    from story.carriers import advance_carriers
    from world.charter_runtime import promotion_bundle

    cid, scene, ctx = _world(temp_db)
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_gate"}]})

    bundle = promotion_bundle(cid, "Mara Venn")
    memory = next(m for m in bundle["handoff"]["memories"]
                  if m["event_key"] == "report:world_gate")
    assert memory["provenance"] == "witnessed"
    assert "the north gate was chained shut" in memory["content"]


def test_later_firsthand_evidence_replaces_a_charter_persons_hearsay(temp_db):
    from story.carriers import advance_carriers
    from world.charter_runtime import carrier_entries, save_carrier_state

    cid, scene, ctx = _world(temp_db)
    mara = next(entry for entry in carrier_entries(cid) if entry["uid"] == "mara")
    save_carrier_state(cid, mara, {"carried_reports": [{
        "world_event_id": "world_gate", "claim": "the gate may be barred",
        "kind": "consequence", "occurred_at": 60.0,
        "acquired_location": "square", "current_location": "square",
        "retellings": 2, "told_by": "a frightened traveller",
        "provenance": "told",
    }]})

    advance_carriers(ctx, scene, {"events": [{"event_id": "world_gate"}]})
    claim = next(iter(_minds(cid)["mara"].values()))
    assert claim["claim_text"] == "the north gate was chained shut"
    assert claim["heard_from"] is None
    assert claim["retellings"] == 0


def test_courier_can_depart_from_one_charter_person_and_deliver_to_another(
        temp_db):
    from story.carriers import advance_carriers
    from story.couriers import run_couriers

    cid, scene, ctx = _world(temp_db)
    temp_db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_gate"}]})
    metrics, rejected = run_couriers(ctx, scene, [{
        "op": "send", "sender": "Mara Venn", "to_room": "road",
        "addressee": "Orin Pell", "world_event_id": "world_gate",
        "method": "letter",
    }])
    assert not rejected and metrics["dispatched"] == 1

    temp_db.wset(cid, "simulation_clock", {"elapsed_seconds": 300.0})
    metrics, rejected = run_couriers(ctx, scene, [])
    heard = next(iter(_minds(cid)["orin"].values()))
    assert not rejected and metrics["courier_delivered"] == 1
    assert heard["claim_text"] == "the north gate was chained shut"
    assert heard["heard_from"]


def test_charter_people_can_post_and_read_the_same_physical_notice(temp_db):
    from story.artifacts import run_artifacts, standing_artifacts
    from story.carriers import advance_carriers
    from world.charter_runtime import registry_for, save_registry

    cid, scene, ctx = _world(temp_db)
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_gate"}]})
    metrics, rejected = run_artifacts(ctx, scene, [{
        "op": "post", "poster": "Mara Venn",
        "world_event_id": "world_gate", "description": "a chalk notice",
    }])
    assert not rejected and metrics["artifacts_posted"] == 1
    artifact_id = standing_artifacts(cid)[0]["uid"]

    registry = registry_for(cid)
    registry["items"]["market"]["state"]["bodies"]["orin"]["place"] = "square"
    save_registry(cid, registry)
    metrics, rejected = run_artifacts(ctx, scene, [{
        "op": "read", "artifact_id": artifact_id, "reader": "Orin Pell",
    }])
    heard = next(iter(_minds(cid)["orin"].values()))
    assert not rejected and metrics["artifacts_read"] == 1
    assert heard["provenance"] == "read"
    assert heard["claim_text"] == "the north gate was chained shut"
