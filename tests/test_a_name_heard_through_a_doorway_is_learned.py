"""A name said by somebody you can see is learned, whichever side of a doorway
they stand on; a body you cannot see teaches you nothing.

Measured on chat 175: at the opening the player stood on the lane a few paces
short of a cottage's open door, and the woman leaning in that doorway said
"I'm Mellisande...". The line reached the player whole ("full via spatial ...
barrier open_door") and the player never learned the name in fourteen turns,
because `_names_heard_in` refused any named body outside the hearer's own
room. Its refusal is right for what it was written for -- hearing ABOUT
somebody absent teaches a name, not a face -- and wrong for a body in plain
view one doorway off. The rule is now that the named body is PERCEIVED: in
the hearer's room, or in their sight (`sighted_level`, at any grade).

The same opening showed the second half of the class: both bodies read
"an indistinct figure" to each other, one open doorway apart in lit
afternoon, because the view cone (`_opening_view_cap`) read only the anchor
field `at` -- empty for both -- and the lane is `vast`, whose
placement-unknown fallback withholds a face. Both bodies stood on measured
cells. The owner, 2026-10-05: distance takes nothing one doorway away.

The lane, the cottage and the names are the chat's shape; the rule is the
class.
"""
from __future__ import annotations

import copy

from persist.commit import _names_heard_in
from world.spatial import _opening_view_cap, sighted_level

ROSTER = ["Hinami", "Mellisande"]
LINE = "I'm Mellisande. You look half drowned -- come in out of the lane."


def _lane_scene(barrier="open_door"):
    """Chat 175's opening: a lane six paces wide and twenty-four long running
    south to a cottage door; the cottage room five by six beyond it. The
    player on the lane at [3, 21]; the cottage woman in the doorway's own
    cell, [2, 0]."""
    lane = {"name": "The Lane", "exposure": "open", "light": "lit",
            "size": "large", "extent": {"w": 6, "d": 24}, "shape": "rectangle",
            "anchors": {},
            "adjacent": [{"to": "lane_end", "barrier": barrier, "dir": "s",
                          "material": "wood", "name": "the cottage door"}]}
    cottage = {"name": "The Lane's End", "exposure": "enclosed", "light": "lit",
               "size": "small", "extent": {"w": 5, "d": 6}, "shape": "rectangle",
               "anchors": {},
               "adjacent": [{"to": "the_lane", "barrier": barrier, "dir": "n",
                             "material": "wood", "name": "the cottage door"}]}
    return {
        "rooms": {"the_lane": lane, "lane_end": cottage},
        "positions": {"Hinami": "the_lane", "Mellisande": "lane_end"},
        "stations": {"Hinami": {"at": None, "near": [], "cell": [3, 21]},
                     "Mellisande": {"at": None, "near": [], "cell": [2, 0]}},
        "entities": {}, "poses": {}, "orientation": {}, "contained": {},
    }


def test_a_name_said_in_an_open_doorway_is_learned_across_it():
    sc = _lane_scene()
    assert _names_heard_in(LINE, "Hinami", ROSTER, sc, "the_lane") == ["Mellisande"]


def test_the_two_either_side_of_the_open_door_see_each_other_whole():
    sc = _lane_scene()
    assert sighted_level(sc, "Hinami", "Mellisande") == "full"
    assert sighted_level(sc, "Mellisande", "Hinami") == "full"


def test_the_cone_reads_a_measured_cell_at_cell_grain():
    """In front of the doorway is in view however far up the lane; a body
    pinned against the lane's own south wall beside the doorframe is not."""
    sc = _lane_scene()
    assert _opening_view_cap(sc, "the_lane", "Hinami", "lane_end") == "full"
    sc["stations"]["Hinami"]["cell"] = [3, 2]
    assert _opening_view_cap(sc, "the_lane", "Hinami", "lane_end") == "full"
    sc["stations"]["Hinami"]["cell"] = [0, 23]
    assert _opening_view_cap(sc, "the_lane", "Hinami", "lane_end") == "none"


def test_a_body_beside_one_standing_in_the_doorway_shares_the_door():
    """Pinned a pace along the lane's south wall from the doorway -- beside
    the doorframe by cell -- but placed `near` a body standing in the
    doorway itself: looking past that shoulder, in view (UNBUILT_WORLD
    §1.162's second half, measured on chat 126 turn 9)."""
    sc = _lane_scene()
    sc["stations"]["Hinami"]["cell"] = [1, 23]
    assert _opening_view_cap(sc, "the_lane", "Hinami", "lane_end") == "none"
    sc["positions"]["Tamamo"] = "the_lane"
    sc["stations"]["Tamamo"] = {"at": "door:lane_end"}
    sc["stations"]["Hinami"]["near"] = ["Tamamo"]
    assert _opening_view_cap(sc, "the_lane", "Hinami", "lane_end") == "full"


def test_a_body_of_unknown_placement_keeps_the_large_room_fallback():
    """No cell and no anchor: placement unknown, and the vast lane's
    fallback still withholds a face across it (S2a, 2026-10-05)."""
    sc = _lane_scene()
    del sc["stations"]["Hinami"]
    assert _opening_view_cap(sc, "the_lane", "Hinami", "lane_end") == "conduct"


def test_somebody_absent_teaches_a_name_and_not_a_face():
    sc = _lane_scene()
    del sc["positions"]["Mellisande"]
    del sc["stations"]["Mellisande"]
    assert _names_heard_in(LINE, "Hinami", ROSTER, sc, "the_lane") == []


def test_a_voice_through_a_shut_door_teaches_no_face():
    """The same doorway shut: the voice may carry, the body is not seen."""
    sc = _lane_scene(barrier="closed_door")
    assert sighted_level(sc, "Hinami", "Mellisande") == "none"
    assert _names_heard_in(LINE, "Hinami", ROSTER, sc, "the_lane") == []


def test_a_body_out_of_the_doorways_view_teaches_no_face():
    """Inside the cottage against its north wall, two paces beside the
    doorframe: the open door does not show her, and her name is not bound."""
    sc = _lane_scene()
    sc["stations"]["Mellisande"]["cell"] = [0, 0]
    assert sighted_level(sc, "Hinami", "Mellisande") == "none"
    assert _names_heard_in(LINE, "Hinami", ROSTER, sc, "the_lane") == []


def test_the_speaker_who_names_a_body_in_view_learns_it_too():
    """`_names_spoken_by` asks the same question with the speaker as hearer:
    the player calling the cottage woman by name from the lane knows it."""
    sc = copy.deepcopy(_lane_scene())
    assert _names_heard_in("Mellisande, is that you?", "Hinami", ROSTER, sc,
                           "the_lane") == ["Mellisande"]
