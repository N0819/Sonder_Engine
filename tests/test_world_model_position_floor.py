"""MASTER-028: a legal declared move must not exempt other bodies from the
physical floor.

`director_resolve`'s floor (`_unreachable_position_writes`) strips any body
written into a room it has no passable route to. Its exempt set once included
EVERY body the diff sent to the declared destination, whatever room that body
started in -- so on any beat with a legal declared move, a co-destined write
from an unrelated room was checked by nothing: with `cell -[wall]- lobby
-[open]- hall`, the player legally walking lobby -> hall exempted a companion
the diff moved cell -> hall straight through the wall. That is the chat-74
failure (a companion walked through a wall while the player's own move was
correctly judged) reopened from the other side of the same guard.

The exemption the backstop is OWED still stands, narrowed to what it owns:
the declared mover, and co-destined bodies starting in the mover's own room,
whose crossing of the judged edge is the same movement (including a contested
crossing the backstop honoured, which the floor's route test would re-refuse).

Second gap, same floor: `_bodies` enumerated only the player, extra players
and registered cast, so an unregistered background presence -- real enough to
be written into `positions`, not real enough for a cast row -- was never
route-checked at all.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data
from tests.helpers import fanout_resolve_agent


def _ctx(temp_db, *, rooms, positions, entities=None, to_room="hall",
         mara_status="active"):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Floor test", "", time.time()))
    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(), "char_mara"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, mara_status, "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "Hotel", "time": "night",
        "rooms": rooms, "positions": positions,
        "entities": entities or {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "move", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Floor test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="move",
                      created=time.time()),
        cast=cast, input="move")
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None,
        "movement": {"to_room": to_room},
        "flow": {"reactors": [], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    return ctx


#: cell and lobby share only a WALL; lobby and hall an open doorway.
WALLED = {
    "cell": {"name": "Cell", "adjacent": [
        {"to": "lobby", "barrier": "wall"}]},
    "lobby": {"name": "Lobby", "adjacent": [
        {"to": "cell", "barrier": "wall"},
        {"to": "hall", "barrier": "open"}]},
    "hall": {"name": "Hall", "adjacent": [
        {"to": "lobby", "barrier": "open"}]},
}


def test_a_legal_declared_move_does_not_exempt_a_body_in_another_room(
        temp_db, monkeypatch):
    """The regression itself: player legally lobby -> hall, diff also sends
    Mara cell -> hall through the wall. Her write must fall to the floor."""
    import agents.director as director

    ctx = _ctx(temp_db, rooms=WALLED,
               positions={"The Stranger": "lobby", "Mara": "cell"})
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        {"state_diff": {"positions": {"The Stranger": "hall",
                                      "Mara": "hall"}}}))

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"].get("The Stranger") == "hall"
    assert "Mara" not in out["state_diff"]["positions"]
    assert any("Unreachable position" in w and "Mara" in w
               for w in ctx.warnings)


def test_a_co_located_body_still_crosses_with_the_honoured_contested_move(
        temp_db, monkeypatch):
    """What the old broad exemption was FOR, kept: a contested crossing the
    backstop honoured extends to a body standing at the same doorway -- the
    floor must not re-refuse the group's shared edge."""
    import agents.director as director

    contested = {
        "lobby": {"name": "Lobby", "adjacent": [
            {"to": "hall", "barrier": "closed_door"}]},
        "hall": {"name": "Hall", "adjacent": [
            {"to": "lobby", "barrier": "closed_door"}]},
    }
    ctx = _ctx(temp_db, rooms=contested,
               positions={"The Stranger": "lobby", "Mara": "lobby"})
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        {"state_diff": {"positions": {"The Stranger": "hall",
                                      "Mara": "hall"}}}))

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"].get("The Stranger") == "hall"
    assert out["state_diff"]["positions"].get("Mara") == "hall"


def test_a_co_destined_body_with_its_own_route_still_passes(
        temp_db, monkeypatch):
    """Narrowing the exemption must not refuse ordinary convergence: a body
    with a passable route of its own to the same destination passes the
    floor on that route."""
    import agents.director as director

    rooms = {
        "cell": {"name": "Cell", "adjacent": [
            {"to": "hall", "barrier": "open"}]},
        "lobby": {"name": "Lobby", "adjacent": [
            {"to": "hall", "barrier": "open"}]},
        "hall": {"name": "Hall", "adjacent": [
            {"to": "lobby", "barrier": "open"},
            {"to": "cell", "barrier": "open"}]},
    }
    ctx = _ctx(temp_db, rooms=rooms,
               positions={"The Stranger": "lobby", "Mara": "cell"})
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        {"state_diff": {"positions": {"The Stranger": "hall",
                                      "Mara": "hall"}}}))

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"].get("The Stranger") == "hall"
    assert out["state_diff"]["positions"].get("Mara") == "hall"


def test_an_unregistered_presence_is_a_body_the_floor_knows(
        temp_db, monkeypatch):
    """A background presence with an entity record but no cast row was
    invisible to `_bodies`, so nothing route-checked it. Every entity kind
    outside `_NEVER_STATIONED_KINDS` reads as a body -- the containment
    module's own rule -- so the clerk's write through the wall is refused."""
    import agents.director as director

    ctx = _ctx(temp_db, rooms=WALLED,
               positions={"The Stranger": "lobby", "hotel_clerk": "cell"},
               entities={"hotel_clerk": {"kind": "person",
                                         "name": "Hotel Clerk"}},
               to_room="hall")
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        {"state_diff": {"positions": {"hotel_clerk": "hall"}}}))

    out = director.director_resolve(ctx, nonce=0)

    assert "hotel_clerk" not in out["state_diff"]["positions"]
    assert any("Unreachable position" in w for w in ctx.warnings)


def test_a_vehicle_stays_a_vehicle(temp_db, monkeypatch):
    """The bodies-only rule survives the widening: a thing that travels on
    transit (or carries an interior) is still not route-checked, because its
    arrival is what creates the dock edge everyone else uses."""
    import agents.director as director

    ctx = _ctx(temp_db, rooms=WALLED,
               positions={"The Stranger": "lobby", "service_lift": "cell"},
               entities={"service_lift": {
                   "kind": "contraption", "name": "Service Lift",
                   "interior_rooms": ["lift_interior"]}},
               to_room="hall")
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        {"state_diff": {"positions": {"service_lift": "hall"}}}))

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"].get("service_lift") == "hall"
