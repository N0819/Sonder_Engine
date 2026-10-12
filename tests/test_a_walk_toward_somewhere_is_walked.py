"""A walk declared toward somewhere is walked -- short of it (PA12).

`arrives=false` says the body does not REACH its destination this beat, never
that it does not move. Where the beat placed the body nowhere, or placed it in
the destination and the approach guard refused that, nothing walked it: the
body ended the beat where it began. Saltmarsh Crossing turn 4650 (scratch
chat 170, 2026-10-11): "she goes out along the quay toward Venn's
counting-room" -- the resolve took her through the Grain Office door, the
guard refused it, and she stood in the harbour office she had walked out of,
six paces from that door, while the page put the quay ahead of her.

Now the walk is walked over the cells by the beat's own paces, toward the
destination's door in the room before it, and recorded under way.
"""
from __future__ import annotations

import types

from agents.director import _guard_approach_is_not_arrival

WHO = "Agnes Holloway"


def _scene(**extra):
    scene = {
        "rooms": {
            "harbour_office": {"name": "Harbour office", "adjacent": [
                {"to": "north_quay", "barrier": "open_door", "distance": "adjacent", "dir": "e"}]},
            "north_quay": {"name": "North quay", "adjacent": [
                {"to": "harbour_office", "barrier": "open_door", "distance": "adjacent", "dir": "w"},
                {"to": "grain_office", "barrier": "open_door", "distance": "adjacent", "dir": "n"}]},
            "grain_office": {"name": "Grain office", "adjacent": [
                {"to": "north_quay", "barrier": "open_door", "distance": "adjacent", "dir": "s"}]},
        },
        "positions": {WHO: "harbour_office"},
        "entities": {"agnes": {"name": WHO, "kind": "person"}},
    }
    scene.update(extra)
    return scene


def _toward(room="grain_office", **extra):
    mv = {"to_room": room, "mover": "self", "arrives": False,
          "why": "to find Mr Ayscough"}
    mv.update(extra)
    return {"movement": mv}


def _guard(diff, interp=None, scene=None):
    ctx, out = types.SimpleNamespace(warnings=[]), {"state_diff": diff}
    _guard_approach_is_not_arrival(ctx, interp or _toward(), diff, scene or _scene(),
                                   WHO, out=out)
    return ctx, out


def test_placed_nowhere_she_walks_as_far_as_the_door_she_is_making_for():
    ctx, out = _guard({"positions": {}})
    assert out["state_diff"]["positions"][WHO] == "north_quay"
    (leg,) = out["travel"]["advanced"]
    assert leg["underway"] and leg["destination"] == "grain_office" and leg["to"] == "north_quay"
    assert out["state_diff"]["poses"][WHO]["posture"]
    assert any("Approach under way" in w for w in ctx.warnings)


def test_refused_the_door_she_still_crossed_the_quay():
    """The guard's own refusal stands -- reaching a building is not entering
    it -- and the walk to its door is walked."""
    ctx, out = _guard({"positions": {WHO: "grain_office"}})
    assert out["state_diff"]["positions"][WHO] == "north_quay"
    assert any("Approach is not arrival" in w for w in ctx.warnings)
    assert any("Approach under way" in w for w in ctx.warnings)


def test_a_destination_next_door_is_walked_to_its_doorway_and_not_through_it():
    ctx, out = _guard({"positions": {}}, interp=_toward("north_quay"))
    assert WHO not in out["state_diff"]["positions"], "still in the room she began in"
    (leg,) = out["travel"]["advanced"]
    assert leg["to"] == "harbour_office" and leg["destination"] == "north_quay"
    assert out["state_diff"]["stations"][WHO]["cell"]


def test_a_body_carried_is_left_to_whoever_carries_it():
    scene = _scene(contained={WHO: {"in": "cart", "mode": "riding"}})
    ctx, out = _guard({"positions": {}}, scene=scene)
    assert out["state_diff"]["positions"] == {}
    assert "travel" not in out


def test_with_no_way_there_she_stays_and_nothing_is_said():
    scene = _scene()
    scene["rooms"]["north_quay"]["adjacent"][1]["barrier"] = "closed_door"
    scene["rooms"]["grain_office"]["adjacent"][0]["barrier"] = "closed_door"
    ctx, out = _guard({"positions": {}}, scene=scene)
    assert out["state_diff"]["positions"] == {}
    assert ctx.warnings == []


def test_a_vessel_heading_somewhere_is_the_vessels_business():
    ctx, out = _guard({"positions": {}}, interp=_toward(mover="skiff"))
    assert out["state_diff"]["positions"] == {}
    assert "travel" not in out


def test_a_declaration_that_arrives_is_still_untouched():
    ctx, out = _guard({"positions": {WHO: "grain_office"}}, interp=_toward(arrives=True))
    assert out["state_diff"]["positions"] == {WHO: "grain_office"}
    assert ctx.warnings == []
