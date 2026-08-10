"""Approach C floor: public surfaces move only inside physical holders."""

from __future__ import annotations

import inspect
import json
import time
import types


def _world(db, *, enabled=True):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Carrier story", "", time.time()))
    chars = []
    for name, uid in (("Mora", "mora_uid"), ("Tavi", "tavi_uid")):
        sheet = json.dumps({"identity": {"name": name, "uid": uid}})
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, sheet, "{}", time.time()))
        db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
        chars.append((char_id, sheet))
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 3, "", time.time()))
    db.wset(cid, "living_world", {
        "rumor_ledger": "floor" if enabled else "off"})
    scene = {
        "rooms": {"square": {"name": "Square", "adjacent": ["road"]},
                  "road": {"name": "Road", "adjacent": ["square"]}},
        "positions": {"Mora": "square", "Tavi": "road"},
    }
    db.qi(
        "INSERT INTO world_events(event_id,chat_id,turn_id,frame_id,"
        "occurred_at,duration_seconds,kind,location_id,payload,seed,committed) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("world_bell", cid, turn_id, None, 50.0, 0.0, "consequence", "square",
         json.dumps({"what": "the hidden mechanism failed",
                     "witnessed": "the warning bell rang twice",
                     "source_event_id": "scheduled_bell"}),
         "seed", time.time()))
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(id=turn_id, idx=3, frame_id=None),
    )
    return cid, chars, scene, ctx


def _state(db, cid, char_id):
    row = db.q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
               (cid, char_id), one=True)
    return json.loads(row["state"] or "{}")


def test_only_the_colocated_character_acquires_the_public_surface(temp_db):
    from carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db)
    result = advance_carriers(
        ctx, scene, {"events": [{"event_id": "world_bell"}]})
    assert result["public_surfaces"] == 1
    assert result["carrier_opportunities"] == result["acquired"] == 1
    mora = _state(temp_db, cid, chars[0][0])["carried_reports"][0]
    assert mora["claim"] == "the warning bell rang twice"
    assert "hidden mechanism" not in json.dumps(mora)
    assert _state(temp_db, cid, chars[1][0]).get("carried_reports") is None


def test_an_unwitnessed_event_emits_nothing(temp_db):
    from carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db)
    temp_db.qi("UPDATE world_events SET payload='{}' WHERE chat_id=?", (cid,))
    result = advance_carriers(
        ctx, scene, {"events": [{"event_id": "world_bell"}]})
    assert result["public_surfaces"] == result["acquired"] == 0
    assert _state(temp_db, cid, chars[0][0]).get("carried_reports") is None


def test_the_setting_gates_acquisition(temp_db):
    from carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db, enabled=False)
    result = advance_carriers(
        ctx, scene, {"events": [{"event_id": "world_bell"}]})
    assert result["enabled"] is False and result["acquired"] == 0
    assert _state(temp_db, cid, chars[0][0]).get("carried_reports") is None


def test_the_envelope_moves_with_its_holder_and_is_not_broadcast(temp_db):
    from carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db)
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
    scene["positions"]["Mora"] = "road"
    result = advance_carriers(ctx, scene, {"events": []})
    report = _state(temp_db, cid, chars[0][0])["carried_reports"][0]
    assert result["carriers_moved"] == 1
    assert report["route"] == ["square", "road"] and report["hops"] == 1
    # Tavi sharing the destination does not learn by proximity or timer.
    assert _state(temp_db, cid, chars[1][0]).get("carried_reports") is None


def test_checkpoint_restore_rewinds_acquisition_and_route(temp_db):
    from carriers import advance_carriers
    from checkpoints import ensure_checkpoint, restore_checkpoint

    cid, chars, scene, ctx = _world(temp_db)
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
    acquired = _state(temp_db, cid, chars[0][0])
    ensure_checkpoint(cid, 4)
    scene["positions"]["Mora"] = "road"
    advance_carriers(ctx, scene, {"events": []})
    restore_checkpoint(cid, 4)
    assert _state(temp_db, cid, chars[0][0]) == acquired


def test_private_projection_is_bounded_and_has_no_hidden_payload():
    from carriers import PAYLOAD_CAP, reports_for_state

    rows = [{"world_event_id": f"e{i}", "claim": f"surface {i}",
             "secret": "never project"} for i in range(PAYLOAD_CAP + 3)]
    projected = reports_for_state({"carried_reports": rows})
    assert len(projected) == PAYLOAD_CAP
    assert [r["world_event_id"] for r in projected] == ["e3", "e4", "e5", "e6"]
    assert all("secret" not in row for row in projected)


def test_carrier_floor_has_no_model_or_provider_call():
    import carriers
    import agents.character as character

    source = inspect.getsource(carriers)
    assert "chat_complete" not in source and "providers" not in source
    character_source = inspect.getsource(character.character_step)
    assert 'payload["carried_reports"]' in character_source
    assert "reports_for_state(stored_state)" in character_source
