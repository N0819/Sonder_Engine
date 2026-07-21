"""prepare_scene_commit applies the mapping agent's scene_patch.remove_rooms
deterministically.

Mapping's scene_patch is otherwise advisory (the Director folds proposals
into state_diff), but models reliably echo room creations while dropping
remove_rooms cleanup -- observed live as a duplicate room the mapping agent
proposed removing on two consecutive turns, with the resolve diff carrying
neither, so the stray room persisted forever. Room removal is map curation,
not causality, so commit applies it directly under conservative guards:
never a room this turn's diff (re)asserts, never an occupied room, never an
entity interior, never a room any transit state still targets.
"""

from __future__ import annotations

import time

from commit import prepare_scene_commit
from db import wset
from pipeline_context import ChatData, PipelineContext, TurnData


def _scene():
    return {
        "location": "Orbital Station", "time": "day",
        "rooms": {
            "deck1_concourse": {"name": "Concourse", "desc": "Hall.",
                                "adjacent": [
                                    {"to": "deck_3", "barrier": "open"},
                                ]},
            "deck3_cargo": {"name": "Cargo Bays (Deck 3)", "desc": "Bays.",
                            "adjacent": []},
            "deck_3": {"name": "Deck 3", "desc": "Duplicate of the bays.",
                       "adjacent": []},
            "lift_car": {"name": "Lift Car", "desc": "Cab.", "adjacent": [],
                         "parent_entity": "lift"},
            "lift_shaft": {"name": "Shaft", "desc": "Shaft.", "adjacent": []},
        },
        "entities": {"lift": {
            "name": "Lift", "kind": "vehicle",
            "interior_rooms": ["lift_car"],
            "state": {"transit": {"phase": "in_transit", "hatch": "closed",
                                  "destination_room": "deck3_cargo",
                                  "route_room": "lift_shaft"}},
        }},
        "positions": {"Rook": "lift_car", "lift": "deck1_concourse"},
        "attire": {}, "overlays": {},
    }


def _make_ctx(temp_db, scene, mapping_patch, state_diff=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 3, "wait", time.time()),
    )
    wset(chat_id, "scene", scene)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=3,
                      player_input="wait", created=time.time(),
                      frame_id=None),
        cast=[], input="wait",
    )
    ctx.director_resolve = {
        "resolved_event": "Time passes.", "dialogue_log": [],
        "state_diff": state_diff or {},
    }
    ctx.mapping_stage = {"scene_patch": mapping_patch}
    return ctx


def test_mapping_remove_rooms_applies_and_scrubs_edges(temp_db):
    ctx = _make_ctx(temp_db, _scene(), {"remove_rooms": ["deck_3"]})
    sc = prepare_scene_commit(ctx)["scene"]
    assert "deck_3" not in sc["rooms"]
    # Dangling adjacency edges into the removed room are scrubbed too.
    edges = [e["to"] for e in sc["rooms"]["deck1_concourse"]["adjacent"]]
    assert "deck_3" not in edges
    # Untouched rooms survive.
    assert "deck3_cargo" in sc["rooms"]


def test_mapping_remove_rooms_guards(temp_db):
    scene = _scene()
    scene["positions"]["Stray NPC"] = "deck_3"
    ctx = _make_ctx(
        temp_db, scene,
        # Every proposal here must be refused: occupied, entity interior,
        # transit route, transit destination.
        {"remove_rooms": ["deck_3", "lift_car", "lift_shaft", "deck3_cargo"]},
    )
    sc = prepare_scene_commit(ctx)["scene"]
    for rid in ("deck_3", "lift_car", "lift_shaft", "deck3_cargo"):
        assert rid in sc["rooms"], rid


def test_mapping_remove_rooms_never_beats_this_turns_diff(temp_db):
    ctx = _make_ctx(
        temp_db, _scene(), {"remove_rooms": ["deck_3"]},
        state_diff={"rooms": {"deck_3": {"name": "Deck 3",
                                         "desc": "Reasserted.",
                                         "adjacent": []}}},
    )
    sc = prepare_scene_commit(ctx)["scene"]
    assert "deck_3" in sc["rooms"]
