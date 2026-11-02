"""The planning gate that decides who is ASKED what they do hears as far as the
hearing rule does -- rooms away included.

Audit world_spatial_sound F7 (2026-11-01, CONFIRMED over-gating):
`can_perceive_onset` graded the ROOM-level `spatial_rel`, which stamps no far
field, so rooms beyond the next read `separated` and only a shout passed. On a
chain of small rooms with open doorways, a cast member two doorways from the
player was never asked (`can_perceive_onset(a, c) == False`) while the
perception layer delivered the player's normal line to them `full`. The
function's own docstring: a gate too tight "is invisible -- the character
simply says nothing and reads as incurious -- so the tie goes to letting them
answer". The owner's ruling: voices carry.
"""

from world.spatial import can_perceive_onset, hear_level, spatial_rel_between


def _chain(barrier="open_door"):
    def room(name, edges):
        return {"name": name, "size": "small", "exposure": "enclosed",
                "adjacent": edges, "anchors": {}}
    return {"rooms": {
        "a": room("A", [{"to": "b", "barrier": barrier, "dir": "e"}]),
        "b": room("B", [{"to": "a", "barrier": barrier, "dir": "w"},
                        {"to": "c", "barrier": barrier, "dir": "e"}]),
        "c": room("C", [{"to": "b", "barrier": barrier, "dir": "w"},
                        {"to": "d", "barrier": barrier, "dir": "e"}]),
        "d": room("D", [{"to": "c", "barrier": barrier, "dir": "w"}]),
        "far": room("Far", []),
    }, "positions": {"P": "a", "C": "c"}, "entities": {}, "stations": {},
        "orientation": {}, "poses": {}, "contained": {}}


def test_a_body_two_doorways_off_that_hears_the_line_is_asked():
    sc = _chain()
    assert hear_level(spatial_rel_between(sc, "C", "P"), "normal") != "none"
    assert can_perceive_onset(sc, "a", "c") is True


def test_rooms_no_voice_reaches_are_still_not_asked():
    sc = _chain(barrier="wall")
    assert can_perceive_onset(sc, "a", "c") is False
    assert can_perceive_onset(_chain(), "a", "far") is False
