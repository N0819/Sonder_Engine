"""Regression tests for the passable-route backstop's over-blocking
(movement/space, observed live in chat 25 turns 3 & 6).

Two failure modes of the pre-fix backstop in director_resolve:

1. Multi-hop over-block: it only accepted a DIRECTLY-adjacent target, so a
   legitimate multi-room walk through open doorways (crew quarters ->
   corridor -> lobby -> engine room) read `separated` and was dropped --
   the narrator described arriving while the committed position never
   moved (prose/state divergence).

2. Same-beat arrive-then-deboard: a vehicle docking THIS beat only gains
   its derived interior->destination dock edge at COMMIT
   (merge_scene_with_diff -> apply_transit_dock_edges), AFTER the
   backstop's route check ran, so an occupant stepping out on the beat the
   vehicle arrives was blocked and stripped.

The fix validates against the beat's would-be merged scene (dock edges
recomputed on a working copy) and allows a non-adjacent target when
spatial.passable_route_exists finds a route whose every doorway is already
open/open_door. A route requiring a still-closed door remains blocked.
"""

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_ctx(temp_db, scene, to_room, mover="self"):
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

    temp_db.wset(chat_id, "scene", scene)

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
        "movement": {"to_room": to_room, "mover": mover},
        "flow": {"reactors": [], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    return ctx


def _station_scene(corridor_to_lobby="open_door"):
    """crew_quarters --open-- corridor --X-- lobby --open_door-- engine_room,
    plus a disconnected isolated_vault. X defaults to open_door (a fully
    passable three-hop chain) and is the knob for the closed-door-mid-path
    case."""
    return {
        "location": "Deep Station",
        "time": "night",
        "rooms": {
            "crew_quarters": {
                "name": "Crew Quarters",
                "adjacent": [
                    {"to": "corridor", "barrier": "open", "distance": "near"},
                ],
            },
            "corridor": {
                "name": "Corridor",
                "adjacent": [
                    {"to": "lobby", "barrier": corridor_to_lobby,
                     "distance": "near"},
                ],
            },
            "lobby": {
                "name": "Lobby",
                "adjacent": [
                    {"to": "engine_room", "barrier": "open_door",
                     "distance": "near"},
                ],
            },
            "engine_room": {"name": "Engine Room", "adjacent": []},
            "isolated_vault": {"name": "Isolated Vault", "adjacent": []},
        },
        "positions": {"The Stranger": "crew_quarters", "Mara": "lobby"},
        "entities": {},
        "attire": {},
        "overlays": {},
    }


def test_multi_hop_walk_through_open_doors_is_committed(temp_db, monkeypatch):
    """Three hops, every doorway open: a real walk, not a teleport. The
    pre-fix backstop saw `separated` (not directly adjacent) and stripped
    the move."""
    import agents.director as director

    ctx = _make_ctx(temp_db, _station_scene(), "engine_room")
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"]["The Stranger"] == "engine_room"
    assert not [w for w in ctx.warnings if "movement" in w.casefold()]


def test_multi_hop_route_through_closed_door_stays_blocked(
    temp_db, monkeypatch,
):
    """The only route to engine_room passes a still-closed door mid-path.
    Multi-hop permissiveness must not turn a closed door into open passage:
    the move stays blocked (and a resolve-asserted position is stripped)
    until the door is opened."""
    import agents.director as director

    ctx = _make_ctx(
        temp_db, _station_scene(corridor_to_lobby="closed_door"),
        "engine_room",
    )
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {"state_diff": {
            "positions": {"The Stranger": "engine_room"}}},
    )

    out = director.director_resolve(ctx, nonce=0)

    assert "The Stranger" not in out["state_diff"]["positions"]
    assert any("Blocked movement" in w for w in ctx.warnings)


def test_multi_hop_route_opened_this_beat_is_committed(temp_db, monkeypatch):
    """A mid-path door the resolve diff opens THIS beat makes the route
    passable -- the beat's diff is merged into the working scene before the
    route check."""
    import agents.director as director

    ctx = _make_ctx(
        temp_db, _station_scene(corridor_to_lobby="closed_door"),
        "engine_room",
    )
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {"state_diff": {"rooms": {"corridor": {
            "name": "Corridor",
            "adjacent": [
                {"to": "lobby", "barrier": "open_door", "distance": "near"},
            ],
        }}}},
    )

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"]["The Stranger"] == "engine_room"
    assert not [w for w in ctx.warnings if "movement" in w.casefold()]


def test_unreachable_target_is_still_blocked_and_stripped(
    temp_db, monkeypatch,
):
    """isolated_vault has no route at all: the multi-hop relaxation must not
    reopen the original teleport hole."""
    import agents.director as director

    ctx = _make_ctx(temp_db, _station_scene(), "isolated_vault")
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {"state_diff": {
            "positions": {"The Stranger": "isolated_vault"}}},
    )

    out = director.director_resolve(ctx, nonce=0)

    assert "The Stranger" not in out["state_diff"]["positions"]
    assert any("Blocked movement" in w for w in ctx.warnings)


def test_directly_adjacent_closed_door_is_still_contested(
    temp_db, monkeypatch,
):
    """The direct-adjacency contract is unchanged: a closed door one room
    away is CONTESTED (the resolve owns the outcome), not silently allowed
    by the route relaxation."""
    import agents.director as director

    scene = _station_scene(corridor_to_lobby="closed_door")
    scene["positions"]["The Stranger"] = "corridor"
    ctx = _make_ctx(temp_db, scene, "lobby")
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)

    assert "The Stranger" not in out["state_diff"]["positions"]
    assert any("Contested movement" in w for w in ctx.warnings)


def _elevator_scene():
    """An elevator in transit up its shaft, the player inside. Its derived
    interior->exterior doorway is a function of entity position + transit
    state, recomputed at merge time (apply_transit_dock_edges)."""
    return {
        "location": "Deep Station",
        "time": "night",
        "rooms": {
            "generator_room": {"name": "Generator Room", "adjacent": []},
            "shaft": {"name": "Elevator Shaft", "adjacent": []},
            "elevator_interior": {
                "name": "Elevator Car",
                "parent_entity": "elevator",
                "adjacent": [],
            },
        },
        "positions": {"elevator": "shaft", "The Stranger": "elevator_interior",
                      "Mara": "generator_room"},
        "entities": {
            "elevator": {
                "name": "the elevator", "kind": "vehicle",
                "aliases": [],
                "interior_rooms": ["elevator_interior"],
                "state": {"transit": {
                    "phase": "in_transit", "hatch": "closed",
                    "route_room": "shaft",
                    "destination_room": "generator_room",
                }},
            },
        },
        "attire": {},
        "overlays": {},
    }


def test_same_beat_vehicle_arrival_allows_occupant_deboard(
    temp_db, monkeypatch,
):
    """The elevator docks at generator_room THIS beat (resolve diff moves
    the entity and flips transit to docked/hatch open) and the player steps
    out in the same beat. The pre-fix backstop route-checked against the
    PRE-merge rooms -- the dock edge did not exist yet -- and stripped the
    player's exit, committing only the elevator's move."""
    import agents.director as director

    ctx = _make_ctx(temp_db, _elevator_scene(), "generator_room")
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {"state_diff": {
            "positions": {"elevator": "generator_room",
                          "The Stranger": "generator_room"},
            "entities": {"elevator": {
                "name": "the elevator", "kind": "vehicle",
                "aliases": [],
                "interior_rooms": ["elevator_interior"],
                "state": {"transit": {"phase": "docked", "hatch": "open"}},
            }},
        }},
    )

    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]

    assert sd["positions"]["The Stranger"] == "generator_room"
    assert sd["positions"]["elevator"] == "generator_room"
    assert not [w for w in ctx.warnings if "Blocked movement" in w]


def test_sealed_vehicle_still_blocks_occupant_exit(temp_db, monkeypatch):
    """Counter-case: nothing docks this beat -- the elevator stays sealed
    in transit -- so the interior has no passable doorway and the asserted
    exit is stripped as before."""
    import agents.director as director

    ctx = _make_ctx(temp_db, _elevator_scene(), "generator_room")
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {"state_diff": {
            "positions": {"The Stranger": "generator_room"}}},
    )

    out = director.director_resolve(ctx, nonce=0)

    assert "The Stranger" not in out["state_diff"]["positions"]
    assert any("Blocked movement" in w for w in ctx.warnings)
