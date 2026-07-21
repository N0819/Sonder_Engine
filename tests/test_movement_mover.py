"""Regression tests for movement.mover (movement/space Phase 1, item 1).

"I drive the van onto the ferry" used to be structurally identical to
"I walk onto the ferry": director_resolve's passable-route backstop always
route-checked and moved the PLAYER's body. With movement.mover set to a
vehicle entity, the backstop must validate the route from the VEHICLE's
position and move the VEHICLE -- the player (and any companion) stays in
its interior, carried implicitly because interior rooms travel with the
entity by identity.
"""

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData
from spatial import merge_scene_with_diff


def _make_ctx(temp_db, movement):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(), "char_mara"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )

    temp_db.wset(
        chat_id,
        "scene",
        {
            "location": "Harbor Approach",
            "time": "day",
            "rooms": {
                "dock_road": {
                    "name": "Dock Road",
                    "adjacent": [
                        {"to": "ferry_deck", "barrier": "open",
                         "distance": "near"},
                    ],
                },
                "ferry_deck": {"name": "Ferry Vehicle Deck", "adjacent": []},
                "cliff_path": {"name": "Cliff Path", "adjacent": []},
                "van_interior": {
                    "name": "Van Interior",
                    "parent_entity": "van",
                    "adjacent": [
                        {"to": "dock_road", "barrier": "open_door",
                         "distance": "near"},
                    ],
                },
            },
            "positions": {
                "van": "dock_road",
                "The Stranger": "van_interior",
                "Mara": "van_interior",
            },
            "entities": {
                "van": {
                    "name": "the van", "kind": "vehicle",
                    "aliases": ["delivery van"],
                    "interior_rooms": ["van_interior"],
                    "state": {},
                },
            },
            "attire": {},
            "overlays": {},
        },
    )

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "drive", time.time()),
    )

    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="drive",
                      created=time.time()),
        cast=cast,
        input="drive",
    )
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None,
        "movement": movement,
        "flow": {"reactors": [], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    return ctx


def test_vehicle_move_updates_entity_position_not_player(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, {"to_room": "ferry_deck", "mover": "van"})
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]

    assert sd["positions"]["van"] == "ferry_deck"
    assert "The Stranger" not in sd["positions"]
    assert "Mara" not in sd["positions"]

    # Merge through the ordinary commit-path merge: the occupants stay in
    # the interior room (carried by identity) and the derived dock edge now
    # opens onto the ferry deck instead of the dock road.
    merged = merge_scene_with_diff(temp_db.wget(ctx.chat.id, "scene", {}), sd)
    assert merged["positions"]["The Stranger"] == "van_interior"
    assert merged["positions"]["Mara"] == "van_interior"
    exterior_edges = [
        e for e in merged["rooms"]["van_interior"]["adjacent"]
        if e.get("to") != "van_interior"
    ]
    assert [e["to"] for e in exterior_edges] == ["ferry_deck"]


def test_vehicle_move_resolves_mover_by_name_or_alias(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, {"to_room": "ferry_deck", "mover": "delivery van"})
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)

    # Written under the key the scene actually stores the entity's
    # position under (the entity id), whatever alias interpret used.
    assert out["state_diff"]["positions"]["van"] == "ferry_deck"


def test_vehicle_move_route_checks_the_vehicle_not_the_player(
    temp_db, monkeypatch,
):
    """The van sits on dock_road (open route to ferry_deck); the PLAYER
    sits inside van_interior. Pre-mover code route-checked from the
    player's room -- which would have judged this same move by the wrong
    edge. A vehicle-declared move into a room with no route from the
    VEHICLE's position must be blocked."""
    import agents.director as director

    ctx = _make_ctx(temp_db, {"to_room": "cliff_path", "mover": "van"})
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)

    assert "van" not in out["state_diff"]["positions"]
    assert any("Blocked movement" in w for w in ctx.warnings)


def test_vehicle_move_strips_conflated_player_position(temp_db, monkeypatch):
    """The resolve LLM asserting the PLAYER also arrived at the vehicle's
    destination while they sit in its interior is exactly the driver
    conflation this field exists to prevent -- strip it."""
    import agents.director as director

    ctx = _make_ctx(temp_db, {"to_room": "ferry_deck", "mover": "van"})
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {"state_diff": {"positions": {
            "van": "ferry_deck", "The Stranger": "ferry_deck"}}},
    )

    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]

    assert sd["positions"]["van"] == "ferry_deck"
    assert "The Stranger" not in sd["positions"]
    assert any("Vehicle movement" in w for w in ctx.warnings)


def test_self_move_still_moves_the_player_body(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, {"to_room": "dock_road", "mover": "self"})
    # Put the player on foot for a plain body move.
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    sc["positions"]["The Stranger"] = "van_interior"
    temp_db.wset(ctx.chat.id, "scene", sc)
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"]["The Stranger"] == "dock_road"
    assert "van" not in out["state_diff"]["positions"]


def test_unknown_mover_falls_back_to_player_with_warning(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, {"to_room": "dock_road", "mover": "the zeppelin"})
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)

    # Safe default: the pre-mover behavior (player-body move), loudly.
    assert out["state_diff"]["positions"]["The Stranger"] == "dock_road"
    assert any("does not resolve" in w for w in ctx.warnings)
