"""A VOICE LEAVING A BUILDING INTO THE OPEN AIR (DESIGN_SOUND_FIELD.md § 16,
round 2 lane B, 2026-10-20; § 14.7's question 8, § 11.8's question 9).

A speaker indoors heard by a listener under the sky through an open door --
or the reverse -- was graded by the opening row: whole at any distance, the
budget of a room's ring radiating through a doorway into the next room's
ring. Under the sky there is no ring on the far side. Real: the doorway is
the SOURCE for the outdoor leg, and the free-field law (6 dB a doubling)
runs from the door to the listener; the indoor leg is what it was -- the
room's ring to the door, or the door's spread into the room.

The class, one test each:

  1. a call from a doorway across a yard is whole; the same call across a
     field is not; an ordinary voice from the back of the room, less again;
  2. the reverse: a voice in the yard reaches the body at the door whole
     and the body across the room by the door's spread into it, falling
     off with the yard's distance;
  3. never charged within one enclosed room, nor across an opening between
     two enclosed rooms (the ring's budget stands there);
  4. the wind bends the outdoor leg, and only that leg;
  5. a speaker INDOORS is not shadowed by facing (the ring faces nowhere);
     a speaker in the yard with their back to the door is, for a bystander.
"""

from __future__ import annotations

from world.spatial import (_door_cells, hear_level, hearing_reason,
                           sound_field, spatial_rel_between)


def _cottage(cells, *, yard="open", weather=None, facing=None):
    """A kitchen eight paces by six with an open door in its east wall onto
    a yard ninety-six paces long. `cells` is {name: (room, (x, y))}; a cell
    of "door" stands the body on the kitchen's doorway cell."""
    sc = {"rooms": {
              "kitchen": {"name": "the kitchen", "exposure": "enclosed",
                          "extent": {"w": 8, "d": 6}, "anchors": {},
                          "adjacent": [{"to": "yard", "barrier": "open_door",
                                        "dir": "e"}]},
              "yard": {"name": "the yard", "exposure": yard,
                       "extent": {"w": 96, "d": 6}, "anchors": {},
                       "adjacent": [{"to": "kitchen", "barrier": "open_door",
                                     "dir": "w"}]}},
          "positions": {k: v[0] for k, v in cells.items()},
          "stations": {}, "entities": {}, "poses": {},
          "orientation": dict(facing or {}), "contained": {}}
    door = _door_cells(sc, "kitchen", "yard", derive=True)[0]
    assert door, "the kitchen's east door has a cell"
    for name, (room, cell) in cells.items():
        sc["stations"][name] = {"cell": list(door[0] if cell == "door" else cell)}
    if weather:
        sc["weather"] = weather
    return sc


def _rel(sc, listener, speaker, **kwargs):
    return spatial_rel_between(sc, listener, speaker,
                               sound=sound_field(sc, listener), **kwargs)


def test_a_call_from_the_doorway_crosses_the_yard_and_not_the_field():
    """A in the doorway, B ten paces out: an ordinary voice is whole. B
    ninety paces out across the field: in pieces, and a raised one whole.
    From the back of the kitchen the same ordinary voice is whole across
    the yard still and lost across the field."""
    yard = _rel(_cottage({"A": ("kitchen", "door"), "B": ("yard", (9, 3))}),
                "B", "A")
    assert yard.get("open_air_loss_db") is not None and yard.get("doorway_air")
    assert hear_level(yard, "normal") == "full"
    field = _rel(_cottage({"A": ("kitchen", "door"), "B": ("yard", (90, 3))}),
                 "B", "A")
    assert hear_level(field, "normal") == "fragment"
    assert hearing_reason(field, "normal") == "open_air_distance"
    assert hear_level(field, "loud") == "full"
    back = _rel(_cottage({"A": ("kitchen", (0, 3)), "B": ("yard", (9, 3))}),
                "B", "A")
    assert hear_level(back, "normal") == "full"
    back_far = _rel(_cottage({"A": ("kitchen", (0, 3)), "B": ("yard", (90, 3))}),
                    "B", "A")
    assert hear_level(back_far, "normal") == "none"
    assert float(back_far["open_air_loss_db"]) > float(field["open_air_loss_db"])


def test_a_voice_in_the_yard_comes_in_by_the_door():
    """B ten paces out in the yard calls to A: at the door A has it whole,
    and across the kitchen whole still by the door's spread into the room;
    B forty paces out, the body across the kitchen has it in pieces."""
    at_door = _rel(_cottage({"A": ("kitchen", "door"), "B": ("yard", (9, 3))}),
                   "A", "B")
    assert at_door.get("open_air_loss_db") is not None
    assert hear_level(at_door, "normal") == "full"
    across = _rel(_cottage({"A": ("kitchen", (0, 3)), "B": ("yard", (9, 3))}),
                  "A", "B")
    assert hear_level(across, "normal") == "full"
    far = _rel(_cottage({"A": ("kitchen", (0, 3)), "B": ("yard", (39, 3))}),
               "A", "B")
    assert hear_level(far, "normal") == "fragment"
    assert hearing_reason(far, "normal") == "open_air_distance"


def test_never_within_one_enclosed_room_nor_between_two():
    """Across the kitchen itself the ring carries an ordinary voice; and
    with the yard roofed in -- a barn beyond the kitchen door -- the opening
    row's budget stands at ninety paces."""
    inside = _rel(_cottage({"A": ("kitchen", (0, 3)), "B": ("kitchen", (7, 3))}),
                  "B", "A")
    assert "open_air_loss_db" not in inside
    assert hear_level(inside, "normal") == "full"
    barn = _rel(_cottage({"A": ("kitchen", "door"), "B": ("yard", (90, 3))},
                         yard="enclosed"), "B", "A")
    assert "open_air_loss_db" not in barn
    assert hear_level(barn, "normal") == "full"


def test_the_wind_bends_the_outdoor_leg():
    """A raised voice from the doorway ninety paces (67 m) into an easterly
    gale is in pieces where in still air it was whole; the bend is stamped,
    the reason says so, and the line graded with no addressee named so the
    gale's din caps nothing here."""
    still = _rel(_cottage({"A": ("kitchen", "door"), "B": ("yard", (90, 3))}),
                 "B", "A")
    assert "wind_bend_db" not in still
    assert hear_level(still, "loud", addressed=None) == "full"
    upwind = _rel(_cottage({"A": ("kitchen", "door"), "B": ("yard", (90, 3))},
                           weather={"sky": "overcast", "cloud": "covered",
                                    "wind": "gale", "wind_from": "e"}),
                  "B", "A")
    assert float(upwind["wind_bend_db"]) < 0.0
    # The bend is folded into the loss (an upwind bend is negative and the
    # loss grows by it), as `stamp_sound_relation` folds it under the sky.
    assert abs(float(upwind["open_air_loss_db"]) + float(upwind["wind_bend_db"])
               - float(still["open_air_loss_db"])) < 1e-6
    assert hear_level(upwind, "loud", addressed=None) == "fragment"
    assert hearing_reason(upwind, "loud", addressed=None) == "upwind"


def test_a_speaker_indoors_is_not_shadowed_by_facing():
    """A at the door with their back to the yard: the ring carries the
    voice to the door whichever way they face, so B ten paces out has it
    whole whoever it was for. B in the yard twenty-five paces out with their
    back to the door: the body at the door, not the one spoken to, loses
    the words the head shades; the one spoken to does not."""
    turned_in = _rel(_cottage({"A": ("kitchen", "door"), "B": ("yard", (9, 3))},
                              facing={"A": {"facing": "w"}}), "B", "A")
    assert not turned_in.get("speaker_turned_away")
    assert hear_level(turned_in, "normal", addressed=False) == "full"
    turned_out = _rel(_cottage({"A": ("kitchen", "door"), "B": ("yard", (24, 3))},
                               facing={"B": {"facing": "e"}}), "A", "B")
    assert turned_out.get("speaker_turned_away") is True
    assert hear_level(turned_out, "normal", addressed=False) == "fragment"
    assert hearing_reason(turned_out, "normal", addressed=False) \
        == "speaker_turned_away"
    assert hear_level(turned_out, "normal", addressed=True) == "full"
