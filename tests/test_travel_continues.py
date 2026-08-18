"""The next step of a walk somebody already declared."""

from world.spatial import passable_route_next_step

SCENE = {"rooms": {
    "forecourt": {"name": "Forecourt", "adjacent": [
        {"to": "hotel", "barrier": "open", "distance": "near"}]},
    "hotel": {"name": "Hotel", "adjacent": [
        {"to": "lobby", "barrier": "open_door", "distance": "adjacent"}]},
    "lobby": {"name": "Lobby", "adjacent": [
        {"to": "back_office", "barrier": "open", "distance": "adjacent"}]},
    "back_office": {"name": "Back office", "adjacent": []},
    "vault": {"name": "Vault", "adjacent": [
        {"to": "lobby", "barrier": "closed_door", "distance": "adjacent"}]},
}}


def test_the_next_room_is_the_first_hop_of_a_shortest_walk():
    assert passable_route_next_step(SCENE, "forecourt", "back_office") == "hotel"
    assert passable_route_next_step(SCENE, "hotel", "back_office") == "lobby"
    assert passable_route_next_step(SCENE, "lobby", "back_office") == "back_office"


def test_standing_in_the_destination_is_no_step_at_all():
    assert passable_route_next_step(SCENE, "lobby", "lobby") is None


def test_a_route_that_needs_a_shut_door_is_no_route():
    """The same rule passable_route_exists follows: only edges passable THIS
    beat make a path, so a walk does not advance through a closed door."""
    assert passable_route_next_step(SCENE, "lobby", "vault") is None


def test_missing_ends_are_not_guessed_at():
    assert passable_route_next_step(SCENE, None, "lobby") is None
    assert passable_route_next_step(SCENE, "lobby", None) is None
    assert passable_route_next_step(SCENE, "lobby", "nowhere") is None


def test_the_hop_is_deterministic_when_two_routes_tie():
    """A rerun must walk the same way. Ties break on room id, so the same
    scene always yields the same step -- reroll and resume-from-stage both
    depend on the diff being a function of the inputs."""
    scene = {"rooms": {
        "start": {"adjacent": [
            {"to": "b_way", "barrier": "open"},
            {"to": "a_way", "barrier": "open"}]},
        "a_way": {"adjacent": [{"to": "end", "barrier": "open"}]},
        "b_way": {"adjacent": [{"to": "end", "barrier": "open"}]},
        "end": {"adjacent": []},
    }}
    assert passable_route_next_step(scene, "start", "end") == "a_way"
    assert passable_route_next_step(scene, "start", "end") == "a_way"


# --- travel that continues across a silent beat ---------------------------
#
# Live, chat 72. The player declared "we'll stay at a hotel then" and walked
# for it; the approach guard correctly refused to put her inside on the beat
# she was only heading there. Then she wrote "You grab the doctors shoulders
# and stare him directly in the eyes" -- no movement at all -- and the engine
# did two contradictory things in the same beat:
#
#   * `commit.py` read the silent beat as ABANDONING the walk and popped
#     `scene.approach`, on the reasoning that "the walker stopped to do
#     something else, and picking the thread back up is a fresh declaration";
#   * a station anchor written by the spatial specialist resolved to the
#     lobby and moved her the exact two rooms the approach guard had refused
#     one beat earlier, through a channel no movement guard inspects.
#
# The accidental channel gave the narratively right answer. The designed one
# said she stopped walking while she was plainly still walking.
#
# The burden is inverted here. Continuing a declared walk EXECUTES the
# player's declaration; stopping without being told is what overrides them.
# So silence continues, and an interruption is the thing that has to be
# established -- by the Director, which owns objective causality and is the
# only stage reading the whole beat, under a deterministic floor it cannot
# argue with.

import json
import time

from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData
from tests.conftest import fanout_resolve_agent

WALK_SCENE = {
    "location": "Ferry Port",
    "time": "night",
    "rooms": {
        "forecourt": {"name": "Forecourt", "adjacent": [
            {"to": "hotel", "barrier": "open", "distance": "near"}]},
        "hotel": {"name": "Hotel", "adjacent": [
            {"to": "lobby", "barrier": "open_door", "distance": "adjacent"}]},
        "lobby": {"name": "Lobby", "adjacent": [
            {"to": "office", "barrier": "open", "distance": "adjacent"}]},
        "office": {"name": "Back Office", "adjacent": []},
    },
    "positions": {"The Stranger": "forecourt", "Mara": "forecourt"},
    "entities": {}, "attire": {}, "overlays": {},
}


def _walk_ctx(temp_db, *, approach=None, scene=None, interp=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}",
         time.time(), "char_mara"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    sc = json.loads(json.dumps(scene or WALK_SCENE))
    if approach is not None:
        sc["approach"] = approach
    temp_db.wset(chat_id, "scene", sc)
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 4, "grab", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=4,
                      player_input="grab", created=time.time()),
        cast=cast, input="grab")
    ctx.director_interpret = interp or {
        "sequence": [{"type": "action", "attempt": "grab his shoulders"}],
        "speech": None, "action": {"attempt": "grab his shoulders"},
        "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    return ctx


def _resolved(**extra):
    out = {"resolved_event": "She grabs his shoulders and holds his eyes.",
           "summary": "A grab.", "dialogue_log": [], "changes_asserted": [],
           "state_diff": {}}
    out.update(extra)
    return out


def test_a_silent_beat_continues_the_walk(temp_db, monkeypatch):
    """The reported oddity, from the other side: she declared no movement,
    and the engine must carry her one leg toward the place she already said
    she was going -- not strand her and not teleport her."""
    import agents.director as director

    ctx = _walk_ctx(temp_db, approach={"The Stranger": {"to_room": "lobby"}})
    monkeypatch.setattr(director, "_agent_json",
                        fanout_resolve_agent(_resolved()))

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"]["The Stranger"] == "hotel"


def test_the_walk_ends_by_arriving_and_the_record_is_cleared(temp_db,
                                                             monkeypatch):
    import agents.director as director

    ctx = _walk_ctx(temp_db, approach={"The Stranger": {"to_room": "hotel"}})
    monkeypatch.setattr(director, "_agent_json",
                        fanout_resolve_agent(_resolved()))

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"]["The Stranger"] == "hotel"
    assert out["travel"]["arrived"] == ["The Stranger"]


def test_the_director_may_say_the_beat_interrupted_the_walk(temp_db,
                                                            monkeypatch):
    """The nuance the engine cannot enumerate lives with the authority that
    owns objective causality and reads the whole beat. Saying so HOLDS the
    position and ends the walk -- picking it up again is a fresh
    declaration, which is what stopping means."""
    import agents.director as director

    ctx = _walk_ctx(temp_db, approach={"The Stranger": {"to_room": "lobby"}})
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        _resolved(travel_interrupted=[
            {"subject": "The Stranger",
             "reason": "She plants herself and takes him by the shoulders."}])))

    out = director.director_resolve(ctx, nonce=0)

    assert "The Stranger" not in (out["state_diff"].get("positions") or {})
    assert out["travel"]["interrupted"][0]["subject"] == "The Stranger"


def test_a_restrained_body_does_not_walk_whatever_anyone_says(temp_db,
                                                              monkeypatch):
    """The deterministic floor, which the Director cannot argue with: a
    body that cannot relocate itself does not drift toward its errand."""
    import agents.director as director

    ctx = _walk_ctx(temp_db, approach={"The Stranger": {"to_room": "lobby"}})
    temp_db.qi(
        "INSERT INTO world_conditions(chat_id,condition_id,subject_id,kind,"
        "payload,active,started_at) VALUES(?,?,?,?,?,1,0)",
        (ctx.chat.id, "held", "The Stranger", "restraint",
         json.dumps({"condition_id": "held", "subject_id": "The Stranger",
                     "kind": "restraint",
                     "state": {"level": "bound", "by": "the Doctor"}})))
    monkeypatch.setattr(director, "_agent_json",
                        fanout_resolve_agent(_resolved()))

    out = director.director_resolve(ctx, nonce=0)

    assert "The Stranger" not in (out["state_diff"].get("positions") or {})


def test_a_walk_whose_route_has_shut_does_not_advance(temp_db, monkeypatch):
    import agents.director as director

    scene = json.loads(json.dumps(WALK_SCENE))
    scene["rooms"]["forecourt"]["adjacent"][0]["barrier"] = "closed_door"
    ctx = _walk_ctx(temp_db, scene=scene,
                    approach={"The Stranger": {"to_room": "lobby"}})
    monkeypatch.setattr(director, "_agent_json",
                        fanout_resolve_agent(_resolved()))

    out = director.director_resolve(ctx, nonce=0)

    assert "The Stranger" not in (out["state_diff"].get("positions") or {})


def test_declaring_a_fresh_move_this_beat_is_left_alone(temp_db, monkeypatch):
    """Continuation only fills a SILENCE. A beat that declares its own
    movement goes through the ordinary movement machinery untouched."""
    import agents.director as director

    ctx = _walk_ctx(temp_db, approach={"The Stranger": {"to_room": "office"}})
    ctx.director_interpret["movement"] = {
        "to_room": "hotel", "mover": "self", "arrives": True}
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        _resolved(state_diff={"positions": {"The Stranger": "hotel"}})))

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"]["The Stranger"] == "hotel"
    assert not (out.get("travel") or {}).get("advanced")


def test_nobody_walks_when_no_walk_was_ever_declared(temp_db, monkeypatch):
    """The common case: no standing approach, no continuation, no position
    written by this path at all."""
    import agents.director as director

    ctx = _walk_ctx(temp_db)
    monkeypatch.setattr(director, "_agent_json",
                        fanout_resolve_agent(_resolved()))

    out = director.director_resolve(ctx, nonce=0)

    assert not (out["state_diff"].get("positions") or {})
    assert not (out.get("travel") or {}).get("advanced")


# --- a station says where you STAND, not which room you are in ------------
#
# Live, chat 72 turn 47. The spatial specialist wrote exactly one station:
# the night clerk `at: "lobby_doorway"`, `near: ["Hinami", "The Doctor"]`.
# That is a correct description of a man standing in the threshold.
#
# `lobby_doorway` is an anchor owned by the BACK OFFICE -- its name for the
# door through to the lobby. The near-group repair resolved the anchor to
# its owning room, called that the group's room, and moved all three people
# into the back office. Its own warning read "contradictory positions were
# {'The Doctor': lobby, 'Hinami': lobby, 'Sleepy Hotel Clerk': lobby}":
# every one of them was in the lobby and it relocated them anyway.
#
# Two things were wrong and both are worth pinning. A threshold anchor names
# the room it leads TO, so anchor ownership is not evidence of which side of
# the door a body is on. And an anchor claim must never outrank agreement --
# `positions` is the ledger, a station is decoration on it.

STATION_SCENE = {
    "location": "Hotel", "time": "night",
    "rooms": {
        "lobby": {"name": "Lobby", "adjacent": [
            {"to": "office", "barrier": "open", "distance": "adjacent"}],
            "anchors": {"desk": {"desc": "Reception desk"}}},
        "office": {"name": "Back Office", "adjacent": [
            {"to": "lobby", "barrier": "open", "distance": "adjacent"}],
            "anchors": {"lobby_doorway": {"desc": "Doorway to the lobby"}}},
    },
    "positions": {"The Stranger": "lobby", "Mara": "lobby"},
    "entities": {}, "attire": {}, "overlays": {},
}


def test_a_station_anchor_cannot_relocate_a_group_that_agrees(temp_db,
                                                              monkeypatch):
    """The back-office teleport. Everyone is already in one room, so there
    is no contradiction to repair and nothing to move."""
    import agents.director as director

    ctx = _walk_ctx(temp_db, scene=STATION_SCENE)
    # The live shape: the resolve DOES write a position for the newcomer, so
    # the repair operates on the real diff. With no `positions` key at all it
    # mutates a throwaway and warns about a move it never made.
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        _resolved(state_diff={
            "positions": {"Mara": "lobby"},
            "stations": {
                "Mara": {"at": "lobby_doorway", "near": ["The Stranger"]}}})))

    out = director.director_resolve(ctx, nonce=0)

    positions = out["state_diff"].get("positions") or {}
    assert positions.get("The Stranger") in (None, "lobby")
    assert positions.get("Mara") in (None, "lobby")


def test_a_genuine_disagreement_resolves_to_the_players_room(temp_db,
                                                             monkeypatch):
    """With a real contradiction there IS something to settle, and the near
    claim is honoured by pulling the others to the player -- never by moving
    the player on the strength of somebody else's station. Their position is
    the most authoritative thing in the scene and it is where the story is
    told from."""
    import agents.director as director

    scene = json.loads(json.dumps(STATION_SCENE))
    scene["positions"]["Mara"] = "office"
    ctx = _walk_ctx(temp_db, scene=scene)
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        _resolved(state_diff={
            "positions": {"Mara": "office"},
            "stations": {
                "Mara": {"at": "lobby_doorway", "near": ["The Stranger"]}}})))

    out = director.director_resolve(ctx, nonce=0)

    positions = out["state_diff"].get("positions") or {}
    assert positions.get("The Stranger") in (None, "lobby"), (
        "the player was relocated by somebody else's station anchor")
    assert positions.get("Mara") == "lobby"
