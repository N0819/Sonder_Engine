"""The opening commit keeps the seeded plan.

`get_scene` seeds a scene with no rooms from every planted skeleton, so
mapping and the Director opened INSIDE the town -- and `prepare_scene_commit`
merged the opening diff onto the STORED scene, `{}`, so the committed opening
held the Director's four rooms and the square's seven planned exits became
one until the fringe restored them on occupation (Harrowmere turn 1: "dropped
exit(s) from bridge_approach to undefined room(s) orrin_shrine, toll_bridge").

The rule: planned adjacency is authority for a planned room. A diff may add
exits to it and may never subtract one; and a room the Director mints under
a planned room's name lands ON the planned room rather than beside it.
"""

from __future__ import annotations

import copy
import json
import os
import time as _time

import pytest

from persist import commit
from world.charter_generate import close_plan
from world.structure import plant_structure

_HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="module")
def town():
    with open(os.path.join(_HERE, "data", "harrowmere_plan.json")) as fh:
        return close_plan(json.load(fh))


def _planted(temp_db, town):
    from core.pipeline_context import ChatData, PipelineContext, TurnData

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Harrowmere", "", _time.time()))
    plant_structure(chat_id, town["structure"], town["rooms"])
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Harrowmere", persona_id=None,
                      lorebook_id=None, scenario="", created=_time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=0, player_input="",
                      created=_time.time()),
        cast=[], input="")
    return chat_id, ctx


def _planned_edges(town):
    return {(uid, e["to"]) for uid, room in town["rooms"].items()
            for e in room["adjacent"]}


def _scene_edges(scene):
    return {(uid, e["to"]) for uid, room in scene["rooms"].items()
            for e in room.get("adjacent") or [] if isinstance(e, dict)}


OPENING = {
    "rooms": {
        "gate_road": {"name": "Gate Road", "desc": "The upland road.",
                      "adjacent": [{"to": "market_square",
                                    "barrier": "open"}]},
        "market_square": {"name": "Market Square",
                          "desc": "Striped awnings and a dry fountain.",
                          "adjacent": [{"to": "gate_road",
                                        "barrier": "open"}]},
    },
    "positions": {"Wren": "gate_road"},
}


def test_every_planned_room_and_edge_survives_turn_zero(temp_db, town):
    chat_id, ctx = _planted(temp_db, town)
    ctx.director_establish = {"state_diff": copy.deepcopy(OPENING)}

    prepared = commit.prepare_scene_commit(ctx)
    scene = prepared["scene"]

    assert set(town["rooms"]) <= set(scene["rooms"])
    missing = _planned_edges(town) - _scene_edges(scene)
    assert not missing, sorted(missing)
    # The Director's own prose landed on the planned room, not beside it.
    assert scene["rooms"]["market_square"]["desc"] == \
        "Striped awnings and a dry fountain."
    assert scene["positions"]["Wren"] == "gate_road"
    assert not [w for w in ctx.warnings if "dropped exit" in w], ctx.warnings


def test_a_room_minted_under_a_planned_name_lands_on_the_planned_room(
        temp_db, town):
    chat_id, ctx = _planted(temp_db, town)
    diff = copy.deepcopy(OPENING)
    diff["rooms"]["town_square"] = diff["rooms"].pop("market_square")
    diff["rooms"]["gate_road"]["adjacent"] = [
        {"to": "town_square", "barrier": "open"}]
    ctx.director_establish = {"state_diff": diff}

    scene = commit.prepare_scene_commit(ctx)["scene"]

    assert "town_square" not in scene["rooms"]
    assert scene["rooms"]["market_square"]["desc"] == \
        "Striped awnings and a dry fountain."


def test_a_story_with_no_plan_is_exactly_as_it_was(temp_db):
    from core.pipeline_context import ChatData, PipelineContext, TurnData

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Bare", "", _time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Bare", persona_id=None,
                      lorebook_id=None, scenario="", created=_time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=0, player_input="",
                      created=_time.time()),
        cast=[], input="")
    ctx.director_establish = {"state_diff": copy.deepcopy(OPENING)}

    scene = commit.prepare_scene_commit(ctx)["scene"]

    assert set(scene["rooms"]) == {"gate_road", "market_square"}


def test_a_later_beat_may_add_an_exit_and_never_lose_one(temp_db, town):
    chat_id, ctx = _planted(temp_db, town)
    ctx.director_establish = {"state_diff": copy.deepcopy(OPENING)}
    opening = commit.prepare_scene_commit(ctx)["scene"]
    temp_db.wset(chat_id, "scene", opening)

    from core.pipeline_context import ChatData, PipelineContext, TurnData
    ctx2 = PipelineContext(
        chat=ctx.chat,
        turn=TurnData(id=2, chat_id=chat_id, idx=1, player_input="",
                      created=_time.time()),
        cast=[], input="")
    # The Director rewrites the square with ONE exit and a new one.
    ctx2.director_resolve = {"state_diff": {"rooms": {
        "market_square": {"name": "Market Square",
                          "adjacent": [{"to": "well_house",
                                        "barrier": "open"}]},
        "well_house": {"name": "Well House",
                       "adjacent": [{"to": "market_square",
                                     "barrier": "open"}]},
    }}}
    scene = commit.prepare_scene_commit(ctx2)["scene"]

    edges = _scene_edges(scene)
    assert ("market_square", "well_house") in edges
    assert not (_planned_edges(town) - edges)


def test_mapping_may_not_remove_a_planned_room(temp_db, town):
    chat_id, ctx = _planted(temp_db, town)
    ctx.director_establish = {"state_diff": copy.deepcopy(OPENING)}
    ctx.mapping_stage = {"scene_patch": {"remove_rooms": ["orrin_shrine"]}}

    scene = commit.prepare_scene_commit(ctx)["scene"]

    assert "orrin_shrine" in scene["rooms"]
