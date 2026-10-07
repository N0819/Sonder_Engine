"""A mind goes only where its own declaration takes it -- the player's included.

Owner ruling, 2026-10-07. Measured on scratch story 166, turn 4587: Hester
declared "turns up the boards toward the low walk, slowing a step so Coyle
falls in beside", the resolve prose walked the PLAYER off the landing stage,
and the encoder filed it as Tamsin's own conduct (`source_entity_id`
persona:21) carried out from Hester's declaration. Story 165 had the mirror
(F46): the player's span wrote Hester's room change. The floor reads the
engine's typed attribution, never the prose, and leaves the world its moves:
a current, a hold, a carry, an inside, and a mind whose own agency is in
play at that stage.
"""

import inspect

from agents import director_prose
from agents.director_prose import a_walk_is_its_owners

PLAYER, PILOT = "Tamsin Coyle", "Hester Gale"
INDEX = {"persona:21": PLAYER, "character:81": PILOT,
         "Garory Haugowlow": "Garory Haugowlow"}
HER_ACT = "turn:9:character:81:2:action"
RESOLVE_INPUTS = [{"entity_id": "character:81", "authority_mode": "autonomous",
                   "events": [{"event_id": HER_ACT, "type": "action"}]}]


def _walk(source, event_id, mover, room="low_walk", extra=None):
    patch = {"positions": {mover: room}, "stations": {mover: {"cell": [0, 2]}}}
    patch.update(extra or {})
    return {"source_entity_id": source, "source_event_id": event_id,
            "event": f"{mover} walks to {room}",
            "movement": {"to_room": room, "mover": mover},
            "transforms": [{"item": mover, "patch": patch}]}


def _run(events, inputs=RESOLVE_INPUTS, scene=None):
    warnings = []
    out = a_walk_is_its_owners(events, inputs, INDEX, scene or {},
                               warn=warnings.append)
    return out, warnings


def test_a_pilots_wish_is_not_the_players_step():
    hers = _walk("character:81", HER_ACT, PILOT)
    follow = _walk("persona:21", HER_ACT, PLAYER)
    out, warnings = _run([hers, follow])
    assert out == [hers], "her own walk stands; the player's invented one does not"
    assert warnings and PLAYER in warnings[0]


def test_the_players_span_does_not_move_another_mind():
    """F46: the player's own event carried the pilot's room change."""
    primary = "turn:9:primary:raw"
    inputs = [{"entity_id": "persona:21", "authority_mode": "world_author",
               "events": [{"event_id": primary, "type": "raw_input"}]}]
    span = _walk("persona:21", primary, PLAYER, room="taproom")
    span["transforms"][0]["patch"]["positions"][PILOT] = "taproom"
    out, _ = _run([span], inputs)
    assert len(out) == 1
    patch = out[0]["transforms"][0]["patch"]
    assert patch["positions"] == {PLAYER: "taproom"}
    assert out[0]["movement"]["mover"] == PLAYER


def test_a_hold_written_this_beat_moves_the_held():
    grip = {"contact_ops": [{"op": "add", "actor": PILOT, "target": PLAYER,
                             "manner": "grip", "relation": "surface",
                             "motion": "moving"}]}
    hers = _walk("character:81", HER_ACT, PILOT, extra=grip)
    follow = _walk("persona:21", HER_ACT, PLAYER)
    out, warnings = _run([hers, follow])
    assert out == [hers, follow] and not warnings


def test_a_standing_hold_moves_the_held():
    scene = {"contacts": [{"actor": PILOT, "target": PLAYER, "manner": "hold"}]}
    follow = _walk("persona:21", HER_ACT, PLAYER)
    out, _ = _run([follow], scene=scene)
    assert out == [follow]


def test_the_world_moves_whom_it_moves():
    inputs = [{"entity_id": "world_pressure:tide", "authority_mode": "world",
               "events": [{"event_id": "tide:1", "type": "due_process"}]}]
    swept = _walk("persona:21", "tide:1", PLAYER, room="the_shallows")
    out, warnings = _run([swept], inputs)
    assert out == [swept] and not warnings


def test_a_mind_with_its_own_say_this_stage_is_the_directors_to_resolve():
    inputs = RESOLVE_INPUTS + [{
        "entity_id": "persona:21", "authority_mode": "world_author",
        "events": [{"event_id": "turn:9:primary:0", "type": "action"}]}]
    hers = _walk("character:81", HER_ACT, PILOT)
    hers["transforms"][0]["patch"]["positions"][PLAYER] = "low_walk"
    out, warnings = _run([hers], inputs)
    assert out == [hers] and not warnings


def test_a_figure_is_the_worlds_to_move():
    primary = "turn:9:primary:raw"
    inputs = [{"entity_id": "persona:21", "authority_mode": "world_author",
               "events": [{"event_id": primary, "type": "raw_input"}]}]
    span = _walk("persona:21", primary, "Garory Haugowlow", room="low_walk")
    out, warnings = _run([span], inputs)
    assert out == [span] and not warnings


def test_the_floor_runs_on_every_encoded_beat():
    source = inspect.getsource(director_prose.run)
    assert "a_walk_is_its_owners(" in source
    assert source.index("a_walk_is_its_owners(") < source.index("ledger_from_events(")
