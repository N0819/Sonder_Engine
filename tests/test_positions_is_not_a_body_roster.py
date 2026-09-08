"""`positions` answers WHERE, not WHO: review 2026-09-07 finding A56.

`scene.positions` is the one map that says where a thing is, so everything
with a where is in it -- bodies, docked vehicles, the zones
`spatial_frames.infer_vehicle_zones` derives, and every fixture, tool and piece
of debris the Director has placed. Two mechanics read it as a roster of bodies:
`_tick_subjects` (a standing condition of a PLACE acts on whoever is in it) and
`unanswered_hazard_subjects` (the world-is-a-party-to-a-contest floor).

Measured on the bench copy of chat 117 (2026-09-08): the live scene held 22
position keys and 2 of them were bodies. The other 20 were fixtures, a pry
bar, a wrecked trolley, spilled drums and an iron bung -- and 19 of those 20
carry an `entities` record, which is the scene saying what they are.

ONE PREDICATE ANSWERS IT (`spatial.scene_names_body`, the rework of A56). It
was four: this floor's, `comfort._is_body`, the contact identity floor's
`_endpoint_is_body`, and `charter_predation._scene_figures_at`, which
subtracted `entities` membership -- and two of them gave OPPOSITE answers for
a subject the scene stands somewhere and records nothing else about. That
tier now falls one way everywhere: such a subject IS a body, because the
error is loud (the vitals sweep says every beat that no body of that name is
in the ledger) where the other direction is silent (a person nobody has
dressed yet, dropped out of a fire with no notice).
"""

from __future__ import annotations

import json

from world.charter_predation import _scene_figures_at
from world.mechanics import mechanics_sweep, unanswered_hazard_subjects
from world.spatial import contact_endpoint_is_body, scene_names_body
from world.survival import AIR_DENIED_KEY, vitals_of


_ROOM = "sub_level_three_utility_core"

#: The one position key of chat 117's live scene that carries no entity
#: record: a bung, standing in the room the cast stands in.
_UNRECORDED = "iron_bung"


def _scene():
    return {
        "rooms": {_ROOM: {"name": "Utility Core"}},
        "positions": {
            "Aurel Voss": _ROOM,
            "Sarah Moon": _ROOM,
            # Two things the scene says what they are, and one it does not --
            # chat 117 held exactly that.
            "emergency_utility_lamp": _ROOM,
            "pry_bar": _ROOM,
            _UNRECORDED: _ROOM,
        },
        "entities": {
            "emergency_utility_lamp": {"kind": "device", "container": False},
            "pry_bar": {"kind": "tool", "container": False},
        },
        "attire": {"Aurel Voss": {"wearing": [], "state": []},
                   "Sarah Moon": {"wearing": [], "state": []}},
        "vitals": {"Aurel Voss": {"air": 1.0, "stamina": 1.0,
                                  "nourishment": 1.0, "injury": 0.0},
                   "Sarah Moon": {"air": 1.0, "stamina": 1.0,
                                  "nourishment": 1.0, "injury": 0.0}},
    }


def _smoke(**payload):
    body = {"severity": 0.8, "tick_interval_seconds": 30,
            "tick": {"vitals": {"air": -0.1}, "percept": "smoke thickens"}}
    body.update(payload)
    return {"condition_id": "%s_smoke" % _ROOM, "subject_id": _ROOM,
            "kind": "smoke", "started_at": 0.0, "expires_at": None,
            "next_tick": 0.0,
            "payload": json.dumps(body, ensure_ascii=False)}


def test_the_predicate_reads_the_body_and_refuses_the_recorded_thing():
    scene = _scene()
    assert scene_names_body(scene, "Sarah Moon")
    for thing in ("emergency_utility_lamp", "pry_bar"):
        assert not scene_names_body(scene, thing), thing


def test_a_subject_the_scene_only_stands_somewhere_is_a_body():
    """Tier 3, stated as the decision it is. A registered mind routinely has
    no entity record and, before it is dressed, no ledger row either; the
    bung has neither for the opposite reason. Counting it costs one loud
    notice a beat, and refusing it would drop the person in silence."""
    scene = _scene()
    assert scene_names_body(scene, _UNRECORDED)


def test_every_reader_of_the_question_gives_one_answer():
    """The two-representations class this closed: `_endpoint_is_body` and the
    comfort copy disagreed about exactly the subject above."""
    scene = _scene()
    for name in scene["positions"]:
        assert contact_endpoint_is_body(scene, name) \
            == scene_names_body(scene, name), name

    state = {"scene": scene, "bodies": {}}
    assert _scene_figures_at(state, _ROOM) == sorted(
        ["Aurel Voss", "Sarah Moon", _UNRECORDED])


def test_a_room_condition_takes_the_air_of_bodies_only():
    scene = _scene()
    _, _ops, notices, _counts = mechanics_sweep(
        scene, {"elapsed_seconds": 60.0}, "f1", [], conditions=[_smoke()])

    assert scene[AIR_DENIED_KEY] == ["Aurel Voss", "Sarah Moon", _UNRECORDED]
    assert vitals_of(scene, "Sarah Moon")["air"] < 1.0
    # And the ledger-miss warning is the report, not the noise: it named the
    # lamp and the bar every beat too, and now names only the one subject the
    # scene says nothing about -- which is the notice that gets it filed.
    missed = [n for n in notices if "no body of that name" in n]
    assert len(missed) == 1
    assert _UNRECORDED in missed[0]
    for thing in ("emergency_utility_lamp", "pry_bar"):
        assert thing not in missed[0]


def test_the_unanswered_hazard_floor_names_bodies_only():
    scene = _scene()
    hazard = {"condition_id": "fire", "subject_id": _ROOM, "kind": "fire",
              "payload": json.dumps({"severity": 0.9})}

    assert unanswered_hazard_subjects(scene, [hazard], None, {}) == [
        "Aurel Voss", "Sarah Moon", _UNRECORDED]


def test_a_body_the_cast_does_not_carry_is_still_a_body():
    """The predicate is the scene's, not the caller's roster. The player is a
    body and is not in `ctx.cast`, so a cast list would have dropped exactly
    the person the floor exists for."""
    scene = _scene()
    hazard = {"condition_id": "fire", "subject_id": _ROOM, "kind": "fire",
              "payload": json.dumps({"severity": 0.9})}

    assert "Sarah Moon" in unanswered_hazard_subjects(
        scene, [hazard], None, {})
