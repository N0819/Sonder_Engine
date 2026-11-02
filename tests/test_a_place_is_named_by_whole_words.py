"""A destination names a held room by its words -- and the tail of a
compound word counts only beside a whole word, never alone.

Audit world_spatial_structure_light F6 (2026-11-01, CONFIRMED WRONG-SCENE):
`scene_room_id`'s word fallback accepted a wanted word that is the TAIL of a
held one (`h.endswith(word)`, three letters or more) with nothing else to
anchor it. Rooms {Walled Garden, Kitchen, Entrance Hall}: "the den" resolved
to the garden; rooms {Cockpit, Main Deck}: "the pit" resolved to the cockpit.
The movement compiler reported the destination known and raised no planning
need, and the Director's binding stood the new place on the held room -- "she
retreats to the den" walked her into the garden and no den was ever built.

Kept: the live case the tail rule was written for -- "Cope's yard" for the
room named "Cope's Boatyard" (scratch play 2026-09-14) -- where one wanted word
is a whole word of the name and only the other is a tail.
"""

from world.spatial import scene_room_id


def _rooms(*names):
    return {"rooms": {name.casefold().replace(" ", "_").replace("'", ""):
                      {"name": name, "adjacent": []} for name in names}}


def test_a_lone_tail_names_no_room():
    assert scene_room_id(_rooms("Walled Garden", "Kitchen", "Entrance Hall"),
                         "the den") == ""
    assert scene_room_id(_rooms("Cockpit", "Main Deck"), "the pit") == ""


def test_a_tail_beside_a_whole_word_still_names_its_room():
    sc = {"rooms": {"copes_boatyard": {"name": "Cope's Boatyard", "adjacent": []},
                    "inn": {"name": "The Inn", "adjacent": []}}}
    assert scene_room_id(sc, "Cope's yard") == "copes_boatyard"


def test_whole_words_still_name_their_room():
    sc = _rooms("Walled Garden", "Kitchen", "Entrance Hall")
    assert scene_room_id(sc, "the garden") == "walled_garden"
    assert scene_room_id(sc, "entrance") == "entrance_hall"
