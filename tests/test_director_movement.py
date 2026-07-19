"""Regression tests for movement adjacency validation in director_resolve.

director_interpret derives `movement.to_room` purely from an LLM reading
of the player's declared intent, with no adjacency check. director_resolve
must not commit a position change into a room with no passable route from
the player's current room -- otherwise a misparsed declaration can
teleport the player through a wall.
"""

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData

def _make_ctx(temp_db, to_room):
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
            "location": "Blackthorn Lighthouse",
            "time": "night",
            "rooms": {
                "keeper_room": {
                    "name": "Keeper's Room",
                    "adjacent": [
                        {"to": "lamp_room", "barrier": "open", "distance": "near"},
                    ],
                },
                "lamp_room": {"name": "Lamp Room", "adjacent": []},
                "cliff_path": {"name": "Cliff Path", "adjacent": []},
            },
            "positions": {"The Stranger": "keeper_room", "Mara": "lamp_room"},
            "entities": {},
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
        (chat_id, 1, "move", time.time()),
    )

    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="move",
                      created=time.time()),
        cast=cast,
        input="move",
    )
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None,
        "movement": {"to_room": to_room},
        "flow": {"reactors": [], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    return ctx

def test_movement_into_disconnected_room_is_blocked(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, "cliff_path")  # no adjacency to keeper_room
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)

    assert "The Stranger" not in out["state_diff"]["positions"]
    assert any("Blocked movement" in w for w in ctx.warnings)

def test_movement_into_adjacent_room_is_applied(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, "lamp_room")  # open adjacency to keeper_room
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"]["The Stranger"] == "lamp_room"
    assert not ctx.warnings

def test_resolve_player_room_prefers_canonical_position_over_declared_movement():
    """A declared `movement.to_room` is only a request for director_resolve
    to validate -- it can be rejected by the passable-route check above.
    _resolve_player_room is used by both the action-onset pass
    (perception_act, before resolution) and the outcome pass
    (perception_outcome, after it). If it trusted the declared destination
    over the actual committed scene position, perception_act would show
    the player as having already arrived before the move is even
    resolved, and perception_outcome would still show them as arrived
    even when director_resolve blocked the move.
    """
    from agents.common import _resolve_player_room

    sc = {
        "positions": {"The Stranger": "keeper_room"},
        "rooms": {
            "keeper_room": {"adjacent": [{"to": "lamp_room", "barrier": "open"}]},
            "lamp_room": {"adjacent": []},
            "cliff_path": {"adjacent": []},
        },
    }
    pers = {"name": "The Stranger"}
    interp = {"movement": {"to_room": "cliff_path"}}

    assert _resolve_player_room(sc, pers, interp, cast=[]) == "keeper_room"

def test_perception_outcome_reflects_committed_move_not_stale_onset_cache(
    temp_db, monkeypatch,
):
    """perception_act caches the player's pre-resolution room in
    ctx["_player_room"] for the onset pass. perception_outcome must
    re-resolve against the post-resolution scene rather than reusing that
    cached value, or a successful move never becomes visible in the
    player's own outcome view (and a blocked move would incorrectly keep
    showing the rejected destination).
    """
    import agents.perception as perception

    ctx = _make_ctx(temp_db, "lamp_room")
    # Simulate perception_act having already cached the pre-move room.
    ctx["_player_room"] = "keeper_room"
    ctx.director_resolve = {
        "resolved_event": "The Stranger moves to the lamp room.",
        "dialogue_log": [],
        "state_diff": {"positions": {"The Stranger": "lamp_room"}},
    }

    monkeypatch.setattr(
        perception, "_agent_json",
        lambda *a, **k: {"views": {"player": "You are in the Lamp Room."}},
    )

    perception.perception_outcome(ctx, nonce=0)

    assert ctx["_player_room"] == "lamp_room"
