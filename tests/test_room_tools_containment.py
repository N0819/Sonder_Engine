"""Containment is the Director's (`story/room_tools.py`, `story/room_frontier.py`).

The Planner may know somebody is contained -- a fact about the world, and
nothing is wrong with it -- but a body's inside (a room whose record carries
`parent_entity`) is never handed to it as a ROOM to plan, route through, or
read as a frontier gap or a dangling reference. Where the world puts a body
is the Director's, and it is transient (owner ruling, 2026-09-03).
"""
from __future__ import annotations

import time

import pytest

from story.room_tools import ToolError, run_tool

PLAYER = "Wren Ashby"


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Inside", "A port at dusk.", time.time()))
    db.wset(cid, "scene", {"location": "Port", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates.",
                      "adjacent": [{"to": "quay", "barrier": "open_door"},
                                   {"to": "loft", "barrier": "open_door"}]},
        "loft": {"name": "Loft", "desc": "Dust.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"}]},
        # Somebody inside somebody: where the world put Pip, not a room.
        "inside_mara": {"name": "inside Mara", "desc": "Dark.",
                        "parent_entity": "Mara",
                        "adjacent": [{"to": "quay", "barrier": "open"}]},
    }, "positions": {PLAYER: "quay", "Mara": "quay", "Pip": "inside_mara"},
        "entities": {"Mara": {"name": "Mara"}}, "attire": {}})
    for i in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid


def test_inspect_rooms_reports_containment_on_the_holder(temp_db):
    cid = _story(temp_db)
    out = run_tool(cid, "inspect_rooms")
    assert "inside_mara" not in {r["id"] for r in out["rooms"]}
    assert out["containment"] == [{"inside": "Mara", "who": ["Pip"],
                                   "holder_room": "quay", "room_id": "inside_mara"}]


def test_inspect_route_never_reaches_an_inside(temp_db):
    cid = _story(temp_db)
    with pytest.raises(ToolError, match="inside of Mara"):
        run_tool(cid, "inspect_route", {"from_room": "quay", "to_room": "inside_mara"})
    out = run_tool(cid, "inspect_route", {"from_room": "quay", "to_room": "loft"})
    assert out["path"] == ["quay", "warehouse", "loft"]
    far = run_tool(cid, "inspect_route", {"from_room": "quay", "to_room": "nowhere_at_all"})
    assert "inside_mara" not in far["reachable"]


def test_inspect_structures_lists_no_inside_as_planned(temp_db):
    cid = _story(temp_db)
    assert "inside_mara" not in run_tool(cid, "inspect_structures")["planned_rooms"]


def test_inspect_contradictions_never_dangles_into_an_inside(temp_db):
    from world.planned_entities import add_planned_entity
    cid = _story(temp_db)
    add_planned_entity(cid, {"kind": "thing", "name": "a swallowed ring",
                             "brief": {"where": "inside_mara"}})
    out = run_tool(cid, "inspect_contradictions")
    assert not any(d.get("where") == "inside_mara" or d.get("room") == "inside_mara"
                   for d in out["dangling"])


def test_the_frontier_counts_no_inside_as_ahead(temp_db):
    from story.room_frontier import rooms_ahead
    cid = _story(temp_db)
    reachable, stubs = rooms_ahead(cid, temp_db.wget(cid, "scene"), "quay", depth=3)
    assert "inside_mara" not in reachable and "inside_mara" not in stubs
    assert reachable == ["loft", "warehouse"]
