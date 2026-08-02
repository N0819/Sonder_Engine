"""A declared destination always exists, and is never sealed off from the map.

Going somewhere is the strongest possible assertion that the place is there —
stronger than naming it, which is why this is keyed on MOVEMENT rather than on
mention. A character can talk about a city all day without the engine minting
it; the moment a body walks toward one, it has to be somewhere for them to
arrive.

This used to happen only as a side effect of lore staging: `prepare_scene_commit`
created the destination if that turn's mapping happened to stage a `layout`
entry, and otherwise not at all. Live (chat 58, t25) the movement targeted
`alley_mouth` — an ANCHOR inside `street_outside`, not a room — nothing staged
layout lore for it, and nothing was made.

The second half matters as much as the first: a room with no adjacency is
unreachable from everywhere, and `spatial_rel` reports `separated`/`far` for it,
which is how an interior falls out of the world.
"""

from __future__ import annotations

import json
import time

import pytest

from commit import prepare_scene_commit
from pipeline_context import ChatData, PipelineContext, TurnData
from spatial import spatial_rel


def _ctx(temp_db, to_room, *, staged_layout=None, start="alley_room"):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Dest", "", time.time()))
    temp_db.wset(chat_id, "scene", {
        "rooms": {start: {"name": "Alley", "adjacent": []}},
        "positions": {"Hinami": start},
    })
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Dest", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=4, player_input="go",
                      created=time.time()),
        cast=[], input="go")
    ctx.director_interpret = {"movement": {"to_room": to_room, "mover": "self",
                                           "arrives": True}}
    ctx.director_resolve = {"state_diff": {}}
    if staged_layout:
        ctx.mapping_stage = {"staged_lore": [
            {"category": "layout", "content": staged_layout}]}
    return ctx


def _scene_after(ctx):
    return (prepare_scene_commit(ctx) or {}).get("scene") or {}


def test_a_destination_with_no_staged_lore_is_still_created(temp_db):
    sc = _scene_after(_ctx(temp_db, "northern_plaza"))
    assert "northern_plaza" in sc.get("rooms", {})


def test_the_new_room_is_reachable_from_where_the_mover_came_from(temp_db):
    sc = _scene_after(_ctx(temp_db, "northern_plaza"))
    rel = spatial_rel(sc, "alley_room", "northern_plaza")
    assert rel["barrier"] != "separated", "the destination is sealed off"
    assert rel["same_room"] is False


def test_staged_layout_lore_still_supplies_the_description(temp_db):
    sc = _scene_after(_ctx(temp_db, "northern_plaza",
                           staged_layout="A wide plaza under broken arcades."))
    room = sc["rooms"]["northern_plaza"]
    assert "broken arcades" in room["desc"]
    assert "broken arcades" in room["notes"]


def test_a_room_that_already_exists_is_never_overwritten(temp_db):
    ctx = _ctx(temp_db, "alley_room")
    sc = _scene_after(ctx)
    assert sc["rooms"]["alley_room"]["name"] == "Alley"


def test_no_movement_creates_nothing(temp_db):
    ctx = _ctx(temp_db, None)
    sc = _scene_after(ctx)
    assert set(sc.get("rooms", {})) == {"alley_room"}


def test_the_derived_name_is_readable(temp_db):
    sc = _scene_after(_ctx(temp_db, "northern_plaza"))
    assert sc["rooms"]["northern_plaza"]["name"] == "Northern Plaza"
