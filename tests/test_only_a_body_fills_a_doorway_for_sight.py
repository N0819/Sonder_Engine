"""A doorway is filled for SIGHT by the same thing that fills it for a walk:
a body. A key dropped on the threshold hides nobody.

Audit world_spatial_movement_sight F8 (2026-11-01, CONFIRMED WRONG-SCENE):
`_hold_doorways` stood EVERY positioned name on a doorway cell at standing eye
height (`posture_class` of a key is `standing`), while the walk's `held_cells`
asks `scene_names_body`. A `brass key` pinned on the hall's doorway cell turned
`body_visibility(Ada, Cass)` through that doorway from visible to
`occluded_by 'brass_key'` -- a lantern set down on a threshold hid the next
room like a person -- and the walk walked straight past it.
"""

from world.spatial import body_visibility, door_cell, walk


def _hall_and_yard():
    return {
        "rooms": {
            "hall": {"name": "hall", "extent": {"w": 6, "d": 6}, "anchors": {},
                     "adjacent": [{"to": "yard", "barrier": "open_door", "dir": "e"}]},
            "yard": {"name": "yard", "extent": {"w": 6, "d": 6}, "anchors": {},
                     "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "w"}]},
        },
        "positions": {"Ada": "hall", "Cass": "yard"},
        "stations": {"Ada": {"at": None, "near": [], "cell": [1, 3]},
                     "Cass": {"at": None, "near": [], "cell": [4, 3]}},
        "entities": {}, "orientation": {}, "attire": {"Ada": {}, "Cass": {}},
    }


def _lined_up(sc):
    door = door_cell(sc, "hall", "yard")
    sc["stations"]["Ada"]["cell"] = [1, door[1]]
    far_door = door_cell(sc, "yard", "hall")
    sc["stations"]["Cass"]["cell"] = [far_door[0] + 1, far_door[1]]
    return door


def test_a_thing_on_the_threshold_hides_nobody():
    sc = _hall_and_yard()
    door = _lined_up(sc)
    assert body_visibility(sc, "Ada", "Cass")["visible"] is True
    sc["entities"]["brass_key"] = {"name": "brass key", "kind": "object",
                                   "portable": True}
    sc["positions"]["brass_key"] = "hall"
    sc["stations"]["brass_key"] = {"at": None, "near": [], "cell": list(door)}
    seen = body_visibility(sc, "Ada", "Cass")
    assert seen["visible"] is True, seen
    assert walk(sc, "Ada", "yard", paces=40)["arrived"]


def test_a_body_on_the_threshold_still_fills_it():
    sc = _hall_and_yard()
    door = _lined_up(sc)
    sc["positions"]["Bram"] = "hall"
    sc["attire"]["Bram"] = {}
    sc["stations"]["Bram"] = {"at": None, "near": [], "cell": list(door)}
    seen = body_visibility(sc, "Ada", "Cass")
    assert seen["visible"] is False and seen["occluded_by"] == "Bram"
