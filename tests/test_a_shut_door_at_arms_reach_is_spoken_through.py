"""Two bodies standing at one shut door, one each side, talk through it.

Measured on chat 177 turn 21: the player stood a pace from the plank door of
a cottage's second room and asked the woman standing beside its other face
"you're looking at me like you want something from me". The line arrived
"...you're... looking... something" (`fragment via spatial; volume normal,
barrier closed_door`) and she answered "What was that?". Both hearing paths
graded the shut door without asking who stood at it: the edge rule's
`closed_door` makes a normal voice a fragment at any range, and the sound
field walked the whole mouth-to-ear path as open-air spreading on top of the
door's own 25 dB -- so two bodies at the door's two faces were priced as if
three paces of air stood between them as well as the door.

The rule: a pair at one doorway, one each side, is at the field's arm's
reach (a path of 0, the convention a pair sharing a cell has) less what the
door takes, and nothing else. The owner, 2026-09-26: voices carry, sound
gating is overzealous. What the door must keep, it keeps: a whisper and a
mutter at arm's reach, a normal voice from across the next room, and a
door of dense stuff.

(The door had in fact been opened two beats earlier and the opening was never
recorded; that is the encoder's half of the class and another lane's fix.)

The landing, the second room and the names are the chat's shape; the rule is
the class.
"""
from __future__ import annotations

from world.spatial import hear_level, spatial_rel_between

VOLUMES = ("whisper", "mutter", "normal", "loud", "shout")


def _upstairs(*, material="wood", weather=True, listener_cell=(1, 1),
              speaker_cell=(0, 0), geometry=True, barrier="closed_door"):
    """Chat 177's upper storey: a two-by-two landing and a three-by-two second
    room, one plank door between them (the landing's west wall, the room's
    east wall). The player on the landing at [0, 0], a pace from the door;
    the woman in the room. Heavy rain on the roof, as it was."""
    door = {"barrier": barrier, "material": material, "offset": 1.0}
    landing = {"name": "The Landing", "exposure": "enclosed", "light": "dim",
               "anchors": {},
               "adjacent": [{"to": "spare", "dir": "w", **door}]}
    spare = {"name": "The Second Room", "exposure": "enclosed", "light": "dim",
             "anchors": {},
             "adjacent": [{"to": "landing", "dir": "e", **door}]}
    if geometry:
        landing.update({"size": "tiny", "extent": {"w": 2, "d": 2}})
        spare.update({"size": "tiny", "extent": {"w": 3, "d": 2}})
    sc = {
        "rooms": {"landing": landing, "spare": spare},
        "positions": {"Hinami": "landing", "Mellisande": "spare"},
        "stations": {
            "Hinami": {"at": None, "near": [], "cell": list(speaker_cell)},
            "Mellisande": {"at": None, "near": [], "cell": list(listener_cell)}},
        "entities": {}, "poses": {}, "orientation": {}, "contained": {},
    }
    if weather:
        sc["weather"] = {"precipitation": "rain", "precipitation_kind": "liquid",
                         "intensity": "heavy", "wind": "breeze", "sky": "overcast",
                         "cloud": "covered"}
    return sc


def _heard(sc, listener="Mellisande", speaker="Hinami"):
    rel = spatial_rel_between(sc, listener, speaker)
    return {v: hear_level(rel, v) for v in VOLUMES}, rel


def test_a_question_asked_through_the_door_at_arms_reach_is_heard_whole():
    heard, rel = _heard(_upstairs())
    # The field places the pair and the air relates them; the verdict is
    # the hearing rule's (2026-10-20), which reads `door_reach`.
    assert rel.get("air") is True, "the field must place the pair"
    assert heard["normal"] == "full"
    assert heard["loud"] == "full" and heard["shout"] == "full"
    assert rel.get("door_reach") is True


def test_the_door_still_keeps_a_whisper_and_a_mutter():
    heard, _rel = _heard(_upstairs())
    assert heard["whisper"] == "none"
    assert heard["mutter"] == "none"


def test_it_is_the_same_both_ways_through_the_door():
    heard, rel = _heard(_upstairs(), listener="Hinami", speaker="Mellisande")
    assert heard["normal"] == "full" and heard["whisper"] == "none"
    assert rel.get("door_reach") is True


def test_from_across_the_next_room_a_normal_voice_still_comes_in_pieces():
    """The woman at the far wall of the second room, three paces from the
    door.

    OVERTURNED 2026-10-20 by the owner's ruling (the hearing rule: "a
    normal voice from someone AT the door is full"): the player speaks AT
    the door, so she is spoken to, not overheard -- the voice crosses the
    door's 25 dB and the tiny room beyond holds it within a few decibels,
    and a path has no direction, so her answer from the far wall comes back
    to him the same way. This pinned `fragment` when the rule asked for
    both bodies at the door, which is the live 177 turn 21 shape (she had
    stepped back from the doorway) and kept its "What was that?". A normal
    voice is muffled through a shut door only when nobody stands at it
    (`tests/test_voices_carry_unless_the_story_stops_them.py`)."""
    heard, rel = _heard(_upstairs(listener_cell=(0, 0)))
    assert rel.get("door_reach") is True
    assert heard["normal"] == "full"
    back, _rel = _heard(_upstairs(listener_cell=(0, 0)),
                        listener="Hinami", speaker="Mellisande")
    assert back["normal"] == "full"
    assert heard["whisper"] == "none"


def test_a_door_of_dense_stuff_keeps_its_loss_at_arms_reach():
    """Iron shifts a door one rung more solid (`_MATERIAL_SOUND_STEPS`): a
    door that really keeps a voice in keeps it at arm's reach too."""
    heard, rel = _heard(_upstairs(material="iron"))
    assert "door_reach" not in rel
    assert heard["normal"] != "full"


def test_the_edge_rule_answers_the_same_where_there_is_no_field():
    """No geometry on either room: the edge model grades the pair, and a shut
    door at arm's reach passes a normal voice whole there too -- and still
    keeps a whisper."""
    sc = _upstairs(geometry=False, weather=False)
    sc["stations"] = {"Hinami": {"at": "door:spare"},
                      "Mellisande": {"at": "door:landing"}}
    heard, rel = _heard(sc)
    assert rel.get("signal") is None, "no field: the edge rule decides"
    assert heard["normal"] == "full"
    assert heard["whisper"] == "none" and heard["mutter"] == "none"
    assert rel.get("door_reach") is True
    # ...and with nobody at the door, the edge rule's shut door as before.
    sc["stations"] = {}
    heard, rel = _heard(sc)
    assert "door_reach" not in rel
    assert heard["normal"] == "fragment"


def test_a_hung_curtain_at_arms_reach_is_spoken_through_too():
    """A doorway closed by a curtain or a hide (`membrane`) is the same
    class: two bodies at it, one each side, talk through it; overheard from
    further off an ordinary voice still comes through it in pieces."""
    sc = _upstairs(geometry=False, weather=False, barrier="membrane",
                   material="")
    sc["stations"] = {"Hinami": {"at": "door:spare"},
                      "Mellisande": {"at": "door:landing"}}
    heard, rel = _heard(sc)
    assert rel.get("signal") is None, "no field: the edge rule decides"
    assert heard["normal"] == "full"
    assert heard["whisper"] == "none"
    sc["stations"] = {}
    heard, _rel = _heard(sc)
    assert heard["normal"] == "fragment"
