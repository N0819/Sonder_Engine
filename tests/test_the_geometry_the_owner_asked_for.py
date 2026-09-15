"""Four geometry classes the owner asked for on 2026-09-15.

1. An open side outdoors is the whole wall, not a one-cell doorway.
2. A body standing in a doorway is the door: a line through the aperture
   meets it, and a walk through it finds it filled.
3. A declared run covers twice a walk's paces, and companions sent with a
   walker walk the same cells at the same pace.
4. Every anchor written states its height and footprint (8 of 924 live
   anchors carried one, so nothing blocked sight or a walk).
"""
import json

import agents.director as director
import agents.director_movement as movement
from llm.prompts import get_prompt_body
from llm.schemas import MovementDecl
from world.spatial import (RUN_PACES_PER_SECOND, anchor_cells, body_visibility,
                           door_cell, held_cells, paces_for, walk)
from tests.test_director_movement import _make_ctx


def _outdoors():
    return {
        "rooms": {
            "lane": {"name": "the lane", "exposure": "open", "extent": {"w": 6, "d": 6},
                     "adjacent": [{"to": "field", "barrier": "open", "dir": "e"},
                                  {"to": "barn", "barrier": "open_door", "dir": "n"}]},
            "field": {"name": "the field", "exposure": "open", "extent": {"w": 6, "d": 6},
                      "adjacent": [{"to": "lane", "barrier": "open", "dir": "w"}]},
            "barn": {"name": "the barn", "exposure": "enclosed", "extent": {"w": 6, "d": 6},
                     "adjacent": [{"to": "lane", "barrier": "open_door", "dir": "s"}]},
        },
        "positions": {"Ada": "lane"}, "stations": {"Ada": {"at": None, "near": [], "cell": [0, 5]}},
        "entities": {},
    }


def test_an_open_side_between_outdoor_cells_is_the_whole_wall():
    sc = _outdoors()
    side = anchor_cells(sc, "lane")["door:field"]
    assert len(side["cells"]) == 6 and all(x == 5 for x, _y in side["cells"])
    assert side["desc"] == "the open side"
    # An indoor doorway on the same lane is still one cell wide.
    assert len(anchor_cells(sc, "lane")["door:barn"]["cells"]) == 1
    # The walker crosses the side where it reaches it, not at its middle.
    assert door_cell(sc, "lane", "field", near=(0, 5)) == (5, 5)
    landed = walk(sc, "Ada", "field", paces=40)
    assert landed["room"] == "field" and landed["arrived"]


def _hall_and_yard():
    return {
        "rooms": {
            "hall": {"name": "hall", "extent": {"w": 6, "d": 6}, "anchors": {},
                     "adjacent": [{"to": "yard", "barrier": "open_door", "dir": "e"}]},
            "yard": {"name": "yard", "extent": {"w": 6, "d": 6}, "anchors": {},
                     "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "w"}]},
        },
        "positions": {"Ada": "hall", "Bram": "hall", "Cass": "yard"},
        "stations": {"Ada": {"at": None, "near": [], "cell": [1, 3]},
                     "Bram": {"at": None, "near": [], "cell": [5, 3]},
                     "Cass": {"at": None, "near": [], "cell": [4, 3]}},
        "entities": {}, "orientation": {},
    }


def test_a_body_in_the_doorway_is_the_door():
    sc = _hall_and_yard()
    door = door_cell(sc, "hall", "yard")
    assert door is not None
    # Ada level with the hall's door, Cass just inside the yard's door, so
    # the line between them threads the aperture and nothing else.
    sc["stations"]["Ada"]["cell"] = [1, door[1]]
    far_door = door_cell(sc, "yard", "hall")
    sc["stations"]["Cass"]["cell"] = [far_door[0] + 1, far_door[1]]
    assert body_visibility(sc, "Ada", "Cass")["visible"] is True
    sc["stations"]["Bram"]["cell"] = list(door)          # Bram fills the doorway
    seen = body_visibility(sc, "Ada", "Cass")
    assert seen["visible"] is False and seen["occluded_by"] == "Bram"
    # And a walk through it is stopped where it stands.
    stopped = walk(sc, "Ada", "yard", paces=40)
    assert stopped["blocked"] and stopped.get("held_by") == "doorway"
    assert stopped["room"] == "hall"
    assert door in held_cells(sc, "hall", walker="Ada")
    # Bram steps aside and the line and the walk are clear again.
    sc["stations"]["Bram"]["cell"] = [5, 0]
    assert body_visibility(sc, "Ada", "Cass")["visible"] is True
    assert walk(sc, "Ada", "yard", paces=40)["arrived"]


def test_a_run_covers_twice_a_walk():
    assert paces_for(10, "run") == round(10 * RUN_PACES_PER_SECOND) == 36
    assert paces_for(10, "walk") == paces_for(10) == 18
    assert MovementDecl(to_room="x", pace="run").pace == "run"


def test_companions_walk_with_the_walker(temp_db, monkeypatch):
    from tests.helpers import fanout_resolve_agent
    ctx = _make_ctx(temp_db, "lamp_room")
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    sc["positions"]["Mara"] = "keeper_room"
    temp_db.wset(ctx.chat.id, "scene", sc)
    monkeypatch.setattr(movement, "paces_for", lambda seconds=None, pace=None: 1)
    # The hand sends Mara to the destination with the mover.
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        {"state_diff": {"positions": {"Mara": "lamp_room"}}}))
    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]
    assert sd["positions"]["The Stranger"] == "keeper_room"     # one pace: not there yet
    assert sd["positions"]["Mara"] == "keeper_room"             # walked with, not teleported
    assert {e["subject"] for e in out["travel"]["advanced"] if e.get("underway")} == {"The Stranger", "Mara"}


def test_every_anchor_is_asked_for_its_height_and_footprint():
    establish = get_prompt_body("director_establish", "en")
    assert "anchors:{anchor_id:{desc, dir, height, footprint}}" in establish
    from llm.prompts import DEFAULT_PROMPTS
    spatial = DEFAULT_PROMPTS["director_spatial"]
    assert "EVERY anchor you write states its `height` and its `footprint`" in spatial
    assert "anchors?:{anchor_id:{desc,dir,height,footprint,opacity?}}" in spatial
    assert "pace: run when the span runs" in get_prompt_body("director_interpret", "en")
