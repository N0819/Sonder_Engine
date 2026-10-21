"""A LAID-OUT STAIR IS ONE STAIRWELL, NOT A THIRD DOORWAY (2026-10-20).

The layout tier makes a stair two rooms -- `<a>__<b>_stair_0` on one storey,
`_stair_1` on the next -- so that each storey has its landing; each half is
`made_by_layout`, both under one `laid_out.plan`, each named in the other's
`laid_out.made`, joined by a `way: stair` edge. The coupling lane priced a
voice leaving a room by its opening (ROOM_COUPLING_DB a doorway), and
charged that flight as a doorway too: a voice up a laid-out house's stair
paid three couplings, and the cottage of chats 177/178 went 51.0 -> 67.0 dB
kitchen to landing and lost a murmur it should keep. The flight inside one
stairwell pays only the flight's own loss; a stair an author drew between
two rooms of their own is a doorway and pays as one.
"""

from __future__ import annotations

from world.spatial import WAY_LOSS_DB, far_field_coupling, room_sound_flood


def _house(laid_out: bool):
    def room(level, **extra):
        return dict({"exposure": "enclosed", "extent": {"w": 4, "d": 4},
                     "level": level, "adjacent": []}, **extra)
    plan = "layout:kitchen"
    s0 = {"made_by_layout": True,
          "laid_out": {"plan": plan, "made": ["kitchen", "stair_1"]}} if laid_out else {}
    s1 = {"made_by_layout": True,
          "laid_out": {"plan": plan, "made": ["stair_0", "landing"]}} if laid_out else {}
    rooms = {
        "kitchen": room(0),
        "stair_0": room(0, extent={"w": 4, "d": 2}, **s0),
        "stair_1": room(1, extent={"w": 4, "d": 2}, **s1),
        "landing": room(1),
    }
    rooms["kitchen"]["adjacent"] = [{"to": "stair_0", "barrier": "open", "width": 3}]
    rooms["stair_0"]["adjacent"] = [
        {"to": "kitchen", "barrier": "open", "width": 3},
        {"to": "stair_1", "barrier": "open", "vertical": "up", "way": "stair"}]
    rooms["stair_1"]["adjacent"] = [
        {"to": "stair_0", "barrier": "open", "vertical": "down", "way": "stair"},
        {"to": "landing", "barrier": "open", "width": 3}]
    rooms["landing"]["adjacent"] = [{"to": "stair_1", "barrier": "open", "width": 3}]
    return {"rooms": rooms, "positions": {}, "entities": {}}


def _flight_coupling(scene):
    return far_field_coupling(scene)["stair_0"]["stair_1"]


def test_the_flight_inside_one_stairwell_pays_only_the_flight():
    assert _flight_coupling(_house(True)) == WAY_LOSS_DB["stair"]


def test_an_authored_stair_between_two_rooms_is_a_doorway():
    assert _flight_coupling(_house(False)) > WAY_LOSS_DB["stair"]


def test_a_voice_up_a_laid_out_stair_pays_one_coupling_fewer():
    """Kitchen to landing: two doorways and a flight, not three doorways."""
    laid = room_sound_flood(_house(True), "kitchen", 60.0, voice=True)
    drawn = room_sound_flood(_house(False), "kitchen", 60.0, voice=True)
    gain = float(laid["landing"]["db"]) - float(drawn["landing"]["db"])
    assert gain > 5.0, (laid["landing"], drawn["landing"])


def test_halves_of_two_different_stairs_are_not_one_stairwell():
    laid = _house(True)
    laid["rooms"]["stair_1"]["laid_out"]["plan"] = "layout:another"
    assert _flight_coupling(laid) > WAY_LOSS_DB["stair"]
