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


def test_canonicalize_positions_folds_character_id_scheme_and_player():
    """Live bug (Enterprise fresh run): the director keyed the SAME person by
    different schemes across a turn -- Data as 'character:29' AND
    'Lt. Commander Data', the player as 'Cmdr. Vale' AND snake 'cmdr_vale' --
    so each acquired two conflicting position entries and name-lookup mislocated
    them. Every scheme must fold to ONE canonical key; unregistered background
    presences are left alone."""
    data = {"id": 29, "sheet": json.dumps(
        {"identity": {"name": "Lt. Commander Data", "uid": "char_data"}})}
    positions = {
        "character:29": "bridge",              # id scheme
        "Lt. Commander Data": "corridor",      # name (the conflicting duplicate)
        "Cmdr. Vale": "bridge",                # player by name
        "cmdr_vale": "turbolift",              # player, snake-case
        "william_riker": "bridge",             # background presence -- untouched
    }
    out = canonicalize_positions(positions, [data], player_name="Cmdr. Vale")
    assert "character:29" not in out                 # id scheme folded
    assert list(out).count("Lt. Commander Data") == 1  # single entry, no dup
    assert "cmdr_vale" not in out                    # player snake folded
    assert list(out).count("Cmdr. Vale") == 1
    assert out.get("william_riker") == "bridge"      # background left alone


def test_canonicalize_positions_id_scheme_needs_id_field():
    """A cast row without an 'id' (legacy shape) must not crash and must not
    invent a character:<id> mapping."""
    row = {"sheet": json.dumps(_doctor_sheet())}  # no 'id'
    out = canonicalize_positions({"character:5": "hall"}, [row])
    assert out == {"character:5": "hall"}  # untouched, no id to match


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

    import agents.perception as perception
    real_act = perception._composer_act

    def capture(ctx_, sc, interp, perceivers, *a, **kw):
        captured["perceivers"] = perceivers
        return real_act(ctx_, sc, interp, perceivers, *a, **kw)

    monkeypatch.setattr(perception, "_composer_act", capture)

    result = perception_act(ctx, nonce=0)

    doctor_perceiver = next(
        p for p in captured["perceivers"] if p["id"] == doctor_id
    )
    # The core assertion: the reactor's room resolves despite the uid key.
    assert doctor_perceiver["room"] == "exterior_grounds"
    assert doctor_perceiver["room_name"] == "Exterior Grounds"
    assert doctor_perceiver["spatial_to_actor"].get("same_room") is True

    view = result["views"][str(doctor_id)]
    assert "unspecified area" not in view
    # Same room as the actor -> the player's action is injected into the view.
    assert "shoji" in view


# ---- the same gap, one layer out: an UNREGISTERED presence ----
#
# canonicalize_positions folds a uid key back onto the name only for a
# REGISTERED cast character. An unregistered background presence is not cast,
# so its key is left as the entity uid by design -- and nothing mapped the
# name back, leaving it unreachable by name from the moment it was placed.
# Live (chat 58, t23): a machine standing in the player's own room with its
# weapon trained on her was resolved to None, so the hearing gate saw
# `spatial_rel(None, room)` -> "remote, no known spatial channel" and dropped
# its line for every observer.

def _presence_scene(entities, positions):
    return {"rooms": {"alley": {"name": "Alley"}, "yard": {"name": "Yard"}},
            "positions": positions, "entities": entities}


def test_unregistered_presence_resolves_by_name():
    sc = _presence_scene(
        {"40af0ac4": {"name": "A Dalek", "aliases": ["the metal thing"]}},
        {"Hinami": "alley", "40af0ac4": "alley"})
    assert cast_room(sc, "A Dalek", []) == "alley"


def test_unregistered_presence_resolves_by_alias():
    sc = _presence_scene(
        {"40af0ac4": {"name": "A Dalek", "aliases": ["the metal thing"]}},
        {"40af0ac4": "alley"})
    assert cast_room(sc, "the metal thing", []) == "alley"


def test_presence_name_outranks_another_presence_alias():
    # Two presences; the query is one's NAME and the other's ALIAS. The name
    # must win -- an alias is a nickname, not an identity.
    sc = _presence_scene(
        {"a1": {"name": "A Dalek", "aliases": []},
         "b2": {"name": "The TARDIS", "aliases": ["A Dalek"]}},
        {"a1": "alley", "b2": "yard"})
    assert cast_room(sc, "A Dalek", []) == "alley"


def test_ambiguous_presence_name_resolves_to_nobody():
    # Two Daleks in two rooms. Guessing is worse than the None every
    # unregistered presence used to get.
    sc = _presence_scene(
        {"a1": {"name": "A Dalek", "aliases": []},
         "a2": {"name": "A Dalek", "aliases": []}},
        {"a1": "alley", "a2": "yard"})
    assert cast_room(sc, "A Dalek", []) is None


def test_presence_falls_back_to_its_own_room_field():
    sc = _presence_scene({"a1": {"name": "A Dalek", "room": "yard"}}, {})
    assert cast_room(sc, "A Dalek", []) == "yard"


def test_unknown_presence_name_is_still_none():
    sc = _presence_scene({"a1": {"name": "A Dalek"}}, {"a1": "alley"})
    assert cast_room(sc, "Something Else Entirely", []) is None


def test_registered_cast_still_wins_over_the_entity_table():
    # The entity fallback runs LAST. A real cast character with the same name
    # must still resolve through its sheet, not through a stray entity row.
    sheet = _doctor_sheet()
    sc = {"rooms": {"alley": {"name": "Alley"}, "yard": {"name": "Yard"}},
          "positions": {"tenth_doctor": "alley", "ghost": "yard"},
          "entities": {"ghost": {"name": "The Doctor"}}}
    cast = [{"id": 1, "sheet": json.dumps(sheet), "cstate": "{}",
             "status": "active"}]
    assert cast_room(sc, "The Doctor", cast) == "alley"


def test_presence_lookup_survives_a_scene_with_no_entities():
    sc = {"rooms": {}, "positions": {"Hinami": "alley"}}
    assert cast_room(sc, "A Dalek", []) is None
