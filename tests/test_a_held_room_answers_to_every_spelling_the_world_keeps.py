"""A room the world holds is held under every spelling the world keeps for it.

The prose Director resolves a destination through the room registry's
aliases (`director_prose.destination_place`, `room_aliases`); the compiler did
not, and the vessel reader compared `destination_room` to the scene's keys
exactly (audit of 2026-11-01, agents_runtime_loops_mapping F7/F8,
world_misc_causal F8). So a walk to a renamed room's old name was filed as an
unplanned destination and left un-canonicalised for the commit's destination
ledgers -- the chat-114 split `canonical_movement` exists to prevent -- and a
ferry bound for "Cope's Boatyard" asked the Writers' Room to plan a duplicate
of the yard the scene holds as `copes_boatyard`. With no destination at all,
the need was filed under the vessel's own name: chats 154, 157 and 158 of the
owner's database each hold an open `room:the tardis` need, chat 154's scene
holding `tardis_console_room` inside that very vessel.
"""

from __future__ import annotations

import json
import time

import pytest

import agents.mapping as mapping
from core.db import wset
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _nothing(_query):
    return None


def test_a_walk_under_an_alias_the_compiler_is_given_is_known():
    scene = {"rooms": {"mill_kitchen": {"name": "Kitchen"}}}
    out = mapping.classify_movement(
        {"movement": {"to_room": "Scullery"}}, scene, planned_for=_nothing,
        aliases={"mill_kitchen": ["Scullery"]})
    assert out == {"to_room": "mill_kitchen", "status": "known",
                   "declared_as": "Scullery"}


@pytest.fixture
def no_retrieval(monkeypatch):
    monkeypatch.setattr(mapping, "search_lore", lambda *a, **k: [])


def _ctx(db, scene, interp):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Spellings", "", time.time()))
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 6, "go", time.time()))
    wset(cid, "scene", scene)
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Spellings", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=6, player_input="go",
                      created=time.time()),
        cast=[], input="go")
    ctx.director_interpret = interp
    return ctx


def test_the_compiler_reads_the_registrys_aliases_for_a_held_room(
        temp_db, no_retrieval):
    """The room minted as "Scullery" and renamed "Kitchen": the registry keeps
    the old name, and the Director's beat still says it."""
    scene = {"rooms": {"mill_kitchen": {"name": "Kitchen", "adjacent": []}},
             "positions": {"Wren": "mill_kitchen"}}
    ctx = _ctx(temp_db, scene, {"sequence": [], "flow": {}, "movement": {
        "to_room": "Scullery", "why": "to wash up"}})
    temp_db.qi(
        "INSERT INTO room_registry"
        "(chat_id,room_uid,owning_book_id,parent_entity,name,aliases,payload) "
        "VALUES(?,?,?,?,?,?,?)",
        (ctx.chat.id, "mill_kitchen", None, None, "Kitchen",
         json.dumps(["Scullery"]), json.dumps({})))
    out = mapping.compile_world_context(ctx, nonce=0)
    assert out["movement"] == {"to_room": "mill_kitchen", "status": "known",
                               "declared_as": "Scullery"}
    assert out["planning_needs"] == []


def _ferry_scene(transit, *, name="The Ferry"):
    return {
        "rooms": {
            "copes_boatyard": {"name": "Cope's Boatyard", "adjacent": []},
            "open_water": {"name": "Open Water", "adjacent": []},
            "ferry_cabin": {"name": "Cabin", "parent_entity": "ferry",
                            "adjacent": []},
        },
        "entities": {"ferry": {"name": name, "state": {"transit": transit}}},
        "positions": {"ferry": "open_water"},
    }


def test_a_vessel_bound_for_a_held_room_spelled_by_its_name_raises_no_need():
    scene = _ferry_scene({"phase": "in_transit", "eta_seconds": 600,
                          "destination_room": "Cope's Boatyard",
                          "route_room": "open_water"})
    needs = mapping._transit_destination_needs(
        scene, _nothing, turn_idx=3, frame_id=None)
    assert needs == []


def test_a_vessel_bound_for_a_renamed_rooms_old_name_raises_no_need():
    scene = _ferry_scene({"phase": "in_transit", "eta_seconds": 600,
                          "destination_room": "Cope's Old Slip",
                          "route_room": "open_water"})
    needs = mapping._transit_destination_needs(
        scene, _nothing, turn_idx=3, frame_id=None,
        aliases={"copes_boatyard": ["Cope's Old Slip"]})
    assert needs == []


def test_a_vessel_bound_nowhere_is_one_need_about_the_vessel_not_a_room_named_for_it():
    scene = _ferry_scene({"phase": "in_transit", "eta_seconds": 600,
                          "route_room": "open_water"}, name="The TARDIS")
    needs = mapping._transit_destination_needs(
        scene, _nothing, turn_idx=3, frame_id=None)
    assert [n["reason"] for n in needs] == ["transit_destination_unplanned"]
    need = needs[0]
    assert need["kind"] == "room"
    # never filed as a room CALLED the vessel: that is the room the Room
    # would build, and it would collide with a real room of that name
    assert need["identity"] != "room:the tardis"
    assert need["subject"].casefold() != "the tardis"
    assert need["surface"]["vehicle"] == "ferry"
    again = mapping._transit_destination_needs(
        scene, _nothing, turn_idx=4, frame_id=None)
    assert again[0]["identity"] == need["identity"], "one need per vessel"
