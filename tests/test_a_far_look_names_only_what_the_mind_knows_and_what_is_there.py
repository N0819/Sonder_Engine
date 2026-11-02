"""A look at a far place names it only as the looking mind knows it, and
says what stands in the way only where something does.

THE AUDIT (2026-11-01, world_misc_causal), both reproduced:

* F1, a LEAK: `looked_far` labelled a place the mind never learned by the
  room's own name whenever the look word matched the room's id -- and the
  encoder's card writes the id ("its id where world_index gives one"). A
  stranger looking east was told "To the east, you can see Gale Green", and
  a look at the walled orchard "Toward Widow Marsh's Orchard, ..." -- a
  place's name and a person's name in it. The standing view never did this
  (ruling 3: a far place is named only once the mind knows it).
* F6: a look the walk never answered was told "the buildings around you
  stand between you and it" whatever the reason: on all-open ground behind a
  wall (there are no buildings), past the standing view's cap of 32 graded
  places (cut alphabetically within a hop count), and to a body that sees
  nothing. The owner forbids placeholders: a real occluder, or nothing.

Hand-made scenes; the names are illustrations, not the rule.
"""
from __future__ import annotations

from world.landscape import PLACES_GRADED_MAX, looked_far
from world.scene_memo import scene_read_pass

DIRS = ["n", "ne", "e", "se", "s", "sw", "w", "nw"]


def _lines(scene, looks, known=None, senses=None):
    from agents import composer
    with scene_read_pass(scene):
        found = looked_far(scene, "Ada", looks, known=known, senses=senses)
    return found, [p.data["desc"] for p in composer.landscape_look_percepts(found)]


def _green():
    rooms = {
        "yard": {"name": "Yard", "exposure": "open", "adjacent": [{"to": "lane", "dir": "e"}]},
        "lane": {"name": "Lane", "exposure": "open",
                 "adjacent": [{"to": "yard", "dir": "w"}, {"to": "gale_green", "dir": "e"},
                              {"to": "orchard", "dir": "n", "barrier": "wall"}]},
        "gale_green": {"name": "Gale Green", "exposure": "open",
                       "adjacent": [{"to": "lane", "dir": "w"}]},
        "orchard": {"name": "Widow Marsh's Orchard", "exposure": "open",
                    "adjacent": [{"to": "lane", "dir": "s", "barrier": "wall"}]},
    }
    return {"rooms": rooms, "positions": {"Ada": "yard"}, "entities": {},
            "day_phase": "noon", "weather": {}}


KNOWS = {"yard": "Yard", "lane": "Lane"}      # neither far place learned


def test_a_stranger_s_look_by_id_is_told_no_name():
    found, lines = _lines(_green(), ["gale_green"], known=KNOWS)
    assert found and found[0]["place"]
    assert lines and "Gale" not in lines[0] and "Green" not in lines[0], lines
    _found, lines = _lines(_green(), ["gale_green"], known=dict(KNOWS, gale_green="Gale Green"))
    assert "Gale Green" in lines[0]


def test_no_person_s_name_reaches_a_look_through_a_place_s_name():
    for look in ("orchard", "Widow Marsh's Orchard"):
        _found, lines = _lines(_green(), [look], known=KNOWS)
        assert not any("Marsh" in line for line in lines if look == "orchard"), lines
        assert not any("buildings around you" in line for line in lines), lines


def test_a_named_wall_is_what_a_look_is_told():
    scene = _green()
    for room, to in (("lane", "orchard"), ("orchard", "lane")):
        for edge in scene["rooms"][room]["adjacent"]:
            if edge["to"] == to:
                edge["name"] = "the orchard wall"
    _found, lines = _lines(scene, ["orchard"], known=KNOWS)
    assert lines == ["Toward orchard, the orchard wall stands between you and it."]


def test_a_place_past_the_graded_cap_is_answered_as_seen():
    rooms = {"yard": {"name": "Yard", "exposure": "open", "adjacent": [{"to": "hub", "dir": "e"}]},
             "hub": {"name": "Hub Green", "exposure": "open", "adjacent": [{"to": "yard", "dir": "w"}]}}
    for i in range(PLACES_GRADED_MAX + 8):
        rid = f"spoke{i:02d}"
        rooms[rid] = {"name": f"Spoke Meadow {i:02d}", "exposure": "open",
                      "adjacent": [{"to": "hub", "dir": "w"}]}
        rooms["hub"]["adjacent"].append({"to": rid, "dir": DIRS[i % 8]})
    scene = {"rooms": rooms, "positions": {"Ada": "yard"}, "entities": {},
             "day_phase": "noon", "weather": {}}
    last = f"spoke{PLACES_GRADED_MAX + 7:02d}"
    found, lines = _lines(scene, [last], known={r: rooms[r]["name"] for r in rooms})
    assert [f["room"] for f in found] == [last] and found[0]["place"], found
    assert not any("around you" in line for line in lines)


def test_an_eye_that_sees_nothing_is_told_no_occluder():
    blind = [{"channel": "sight", "acuity": "blind"}]
    found, lines = _lines(_green(), ["gale_green"], known=KNOWS, senses=blind)
    assert found == [] and lines == []
