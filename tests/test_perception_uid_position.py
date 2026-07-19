"""Regression tests for perception resolving a cast character's room when the
scene keys that character's position by its identity.uid (or an alias) rather
than its display name.

Observed bug (chat "Tamamo and the doc dooc"): director_establish keyed the
Doctor's position by identity.uid `tenth_doctor`, but perception looked the
room up by character_name "The Doctor". `room_of` cannot bridge those two
strings, so perception_act placed the Doctor in "an unspecified area" and its
view leaked a degenerate empty perception even though the Doctor was standing
in the same room as the acting player.

Fix is belt-and-suspenders: reads (character_room / cast_room) tolerate uid/
alias keys, and writes (canonicalize_positions in the director) fold a uid key
back onto the registered name.
"""

from __future__ import annotations

import json
import time

from agents.common import canonicalize_positions, cast_room, character_room
from agents.perception import perception_act
from character_schema import default_character_data, default_persona_data
from pipeline_context import ChatData, PipelineContext, TurnData


def _doctor_sheet():
    sheet = default_character_data("The Doctor")
    sheet["identity"]["uid"] = "tenth_doctor"
    sheet["identity"]["aliases"] = ["The Oncoming Storm"]
    return sheet


# ---- unit-level: the pure helpers -----------------------------------------

def test_character_room_resolves_by_uid_key():
    sheet = _doctor_sheet()
    scene = {"positions": {"tenth_doctor": "exterior_grounds"}}
    assert character_room(scene, sheet) == "exterior_grounds"


def test_character_room_resolves_by_alias_key():
    sheet = _doctor_sheet()
    scene = {"positions": {"The Oncoming Storm": "genkan"}}
    assert character_room(scene, sheet) == "genkan"


def test_character_room_prefers_name_over_uid():
    sheet = _doctor_sheet()
    scene = {"positions": {"The Doctor": "main_hall", "tenth_doctor": "cellar"}}
    assert character_room(scene, sheet) == "main_hall"


def test_cast_room_maps_name_through_uid_keyed_scene():
    row = {"sheet": json.dumps(_doctor_sheet())}
    scene = {"positions": {"tenth_doctor": "exterior_grounds"}}
    assert cast_room(scene, "The Doctor", [row]) == "exterior_grounds"


def test_canonicalize_positions_folds_uid_onto_name():
    row = {"sheet": json.dumps(_doctor_sheet())}
    positions = {"Tamamo": "exterior_grounds", "tenth_doctor": "exterior_grounds",
                 "tardis": "exterior_grounds"}
    out = canonicalize_positions(positions, [row])
    assert out["The Doctor"] == "exterior_grounds"
    assert "tenth_doctor" not in out
    # Non-character keys (the player persona, an object) are untouched.
    assert out["Tamamo"] == "exterior_grounds"
    assert out["tardis"] == "exterior_grounds"


def test_canonicalize_positions_leaves_alias_keys_alone():
    # Writes must NOT match on aliases -- a generic alias could collide with a
    # genuinely separate entity.
    row = {"sheet": json.dumps(_doctor_sheet())}
    out = canonicalize_positions({"The Oncoming Storm": "genkan"}, [row])
    assert out == {"The Oncoming Storm": "genkan"}


# ---- integration: perception_act via a uid-keyed scene --------------------

def test_perception_act_resolves_uid_keyed_reactor_room(temp_db, monkeypatch):
    persona = default_persona_data("Tamamo")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Tamamo", json.dumps(persona), "{}"),
    )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Tamamo test", "", time.time(), persona_id),
    )

    doctor_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("The Doctor", json.dumps(_doctor_sheet()), "{}", time.time(), "char_doc"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, doctor_id, "active", "{}"),
    )

    temp_db.wset(chat_id, "scene", {
        "location": "Shrine of the Golden Fox",
        "time": "afternoon",
        "rooms": {"exterior_grounds": {"name": "Exterior Grounds", "adjacent": []}},
        # The Doctor is keyed by identity.uid, exactly as the director wrote it.
        "positions": {"Tamamo": "exterior_grounds",
                      "tenth_doctor": "exterior_grounds"},
        "entities": {}, "attire": {}, "overlays": {},
    })

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )

    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Tamamo test", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=1,
                      player_input="open the shoji", created=time.time()),
        cast=cast,
        input="open the shoji",
    )
    ctx["_player_room"] = "exterior_grounds"
    ctx.director_interpret = {
        "action": {"attempt": "Tamamo opens the shoji", "visibility": "overt",
                   "conceal_from": [], "targets": []},
        "sequence": [{"type": "action", "attempt": "Tamamo opens the shoji",
                      "visibility": "overt", "event_id": "e1"}],
        "flow": {"reactors": [doctor_id]},
    }

    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["payload"] = payload
        return {"views": {str(p["id"]): f"You are in {p['room_name']}."
                          for p in payload["perceivers"]}}

    monkeypatch.setattr("agents.perception._agent_json", fake_agent_json)

    result = perception_act(ctx, nonce=0)

    doctor_perceiver = next(
        p for p in captured["payload"]["perceivers"] if p["id"] == doctor_id
    )
    # The core assertion: the reactor's room resolves despite the uid key.
    assert doctor_perceiver["room"] == "exterior_grounds"
    assert doctor_perceiver["room_name"] == "Exterior Grounds"
    assert doctor_perceiver["spatial_to_actor"].get("same_room") is True

    view = result["views"][str(doctor_id)]
    assert "unspecified area" not in view
    # Same room as the actor -> the player's action is injected into the view.
    assert "shoji" in view
