"""Bodies that touch are never hidden from each other by the room between
their cells.

A standing contact between two bodies is the strongest closeness fact the
scene records, and it is a measurement: two bodies touching are within
reach, and nothing stands between bodies within reach. The cells a body is
drawn on are a derivation (`spatial_fov.body_cell`), and where the two
disagree it is the derivation that is wrong.

Measured on chat 178, checkpoints 28-35: two bodies lying one on the other on
a one-cell bed in a three-by-two room. The upper body's station named a
blanket `near` before it named the body under her, so `body_cell` seated her
beside the blanket -- two cells off, with a waist-high chest of drawers on the
cell between -- and once both were lying down (eyes below the chest's top)
`body_visibility` found the chest on the line. `sighted_level` fell from
`full` to `none` in both directions while `_measured_intimacy` said they were
touching: every act of hers the beat resolved was refused to the player's
view, and the Director's digest listed each body hidden from the other.

The room, the bed and the names are the chat's shape; the rule is the class.
"""
from __future__ import annotations

import copy

from world.spatial import body_cell, body_visibility, sight_digest, sighted_level

CONTACT = {"actor": "Mellisande", "actor_part": "body", "target": "Hinami",
           "target_part": "body", "manner": "press", "relation": "surface",
           "motion": "settled"}


def _bed_scene(*, contacts=(CONTACT,), light="dim"):
    """The spare room of chat 178: a 3x2 room, a narrow bed of one cell on the
    east wall, a chest of drawers on the cell beside it, a shut door east.
    Hinami lies on the bed; Mellisande lies on Hinami. Her station is the
    bed, `near` the blanket first and Hinami second -- the order the beat
    wrote."""
    spare = {"name": "The Second Room", "exposure": "enclosed", "light": light,
             "size": "tiny", "extent": {"w": 3, "d": 2}, "shape": "rectangle",
             "anchors": {
                 "bed": {"desc": "a narrow iron bedstead", "kind": "bed",
                         "dir": "e", "height": "waist", "footprint": "small",
                         "cell": [2, 0]},
                 "chest": {"desc": "a pine chest of drawers", "dir": "n",
                           "height": "waist", "footprint": "small",
                           "cell": [1, 0]}},
             "adjacent": [{"to": "landing", "barrier": "closed_door",
                           "material": "wood", "dir": "e", "offset": 1.0}]}
    landing = {"name": "The Landing", "exposure": "enclosed", "light": light,
               "extent": {"w": 2, "d": 2}, "anchors": {},
               "adjacent": [{"to": "spare", "barrier": "closed_door",
                             "material": "wood", "dir": "w", "offset": 1.0}]}
    return {
        "rooms": {"spare": spare, "landing": landing},
        "positions": {"Hinami": "spare", "Mellisande": "spare",
                      "blanket": "spare"},
        "entities": {"blanket": {"name": "a heavy wool blanket",
                                 "kind": "object", "portable": True}},
        "stations": {
            "Hinami": {"at": "bed", "near": ["Mellisande"]},
            "Mellisande": {"at": "bed", "near": ["blanket", "Hinami"]},
            "blanket": {"at": "bed", "near": ["Mellisande"]}},
        "poses": {
            "Hinami": {"posture": "supine", "support": "bed",
                       "relative_to": "Mellisande", "relation": "beneath"},
            "Mellisande": {"posture": "prone", "support": "Hinami",
                           "relative_to": "Hinami", "relation": "above"}},
        "contacts": [copy.deepcopy(c) for c in contacts],
        "orientation": {}, "contained": {},
    }


def test_two_bodies_lying_together_see_each_other():
    sc = _bed_scene()
    assert sighted_level(sc, "Hinami", "Mellisande") == "full"
    assert sighted_level(sc, "Mellisande", "Hinami") == "full"
    for a, b in (("Hinami", "Mellisande"), ("Mellisande", "Hinami")):
        line = body_visibility(sc, a, b)
        assert line["visible"] and line["fraction"] == 1.0, line
        assert line["occluded_by"] is None and line["hidden_below"] is None


def test_cells_that_disagree_with_a_contact_do_not_hide_either_body():
    """However the cells came apart -- here a host's pins, which outrank
    every derivation -- two bodies in contact are within reach and the chest
    between their pinned cells is not between them."""
    sc = _bed_scene()
    sc["stations"]["Hinami"]["cell"] = [2, 0]
    sc["stations"]["Mellisande"]["cell"] = [0, 0]
    assert body_cell(sc, "Mellisande") == (0, 0)
    assert body_cell(sc, "Hinami") == (2, 0)
    assert sighted_level(sc, "Hinami", "Mellisande") == "full"
    assert sighted_level(sc, "Mellisande", "Hinami") == "full"
    assert sight_digest(sc, ["Hinami", "Mellisande"])["hidden"] == []
    # ...and the same pins with nothing touching keep the chest between them.
    apart = _bed_scene(contacts=())
    apart["stations"]["Hinami"]["cell"] = [2, 0]
    apart["stations"]["Mellisande"]["cell"] = [0, 0]
    assert sighted_level(apart, "Hinami", "Mellisande") == "none"


def test_the_directors_digest_hides_neither_from_the_other():
    digest = sight_digest(_bed_scene(), ["Hinami", "Mellisande"])
    assert digest["hidden"] == []
    assert "Mellisande" in digest["sees"]["Hinami"]
    assert "Hinami" in digest["sees"]["Mellisande"]


def test_the_body_she_touches_is_the_one_she_is_drawn_beside():
    """Both stations name the bed, hers names the blanket first: the contact
    seats her beside the body under her, not beside the blanket."""
    sc = _bed_scene()
    hx, hy = body_cell(sc, "Hinami")
    mx, my = body_cell(sc, "Mellisande")
    assert max(abs(hx - mx), abs(hy - my)) <= 1, ((hx, hy), (mx, my))


def test_a_contact_the_station_never_wrote_still_comes_first():
    """`effective_station` already derives a `near` link from a standing
    contact and appends it after the authored entries; the order is what
    decided the seat, and the body she touches comes first whether the beat
    wrote it or the contact did."""
    sc = _bed_scene()
    sc["stations"]["Mellisande"]["near"] = ["blanket"]
    hx, hy = body_cell(sc, "Hinami")
    mx, my = body_cell(sc, "Mellisande")
    assert max(abs(hx - mx), abs(hy - my)) <= 1, ((hx, hy), (mx, my))


def test_without_a_contact_the_chest_still_hides_a_body_lying_behind_it():
    """The line check still subtracts where nothing says the two touch: the
    same two lying bodies, no contact between them, the chest on the cell
    between their cells -- out of sight, as before."""
    sc = _bed_scene(contacts=())
    assert body_cell(sc, "Mellisande") == (0, 0)
    assert body_cell(sc, "Hinami") == (2, 0)
    assert sighted_level(sc, "Hinami", "Mellisande") == "none"
    assert body_visibility(sc, "Hinami", "Mellisande")["visible"] is False


def test_touch_lights_nothing():
    """A contact is a channel for touch, not for light: in the dark the two
    still do not see each other, and the contact delivers what closeness in
    darkness gives."""
    sc = _bed_scene(light="dark")
    assert sighted_level(sc, "Hinami", "Mellisande") == "none"
    assert sighted_level(sc, "Mellisande", "Hinami") == "none"
