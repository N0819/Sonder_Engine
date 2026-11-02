"""A window pays a walker once, and walks no body the scene has on loan.

Two defects in the window's movement (audit world_charter_behaviours F14,
F15):

  * `continue_walks` skipped only bodies not en route or unavailable, while
    `walk()` honours the lease (ON SCREEN, THE SCENE MOVES IT, owner
    2026-09-14). A walk written onto a leased body was advanced by the next
    tick, and the next commit's lease snapped it back and dropped the errand.
    An errand for a body the scene stands is now refused by name.
  * `continue_walks` credited the window and dropped the leftover on arrival;
    `_dispatch` then granted a FRESH window's credit to the same body
    re-posted the same window. Measured: one room's credit (1/6 h), two
    rooms crossed. What is left of the window is what the next walk gets.
"""
import pytest

from world.charter import normalize_charter
from world.charter_move import (WALK_ROOMS_PER_HOUR, continue_walks,
                                edge_cost, relocate)
from world.charter_surgery import send_errand


def _line():
    # a - b - c - d, one room per leg.
    rooms = {"a": {"name": "A", "adjacent": [{"to": "b"}]},
             "b": {"name": "B", "adjacent": [{"to": "a"}, {"to": "c"}]},
             "c": {"name": "C", "adjacent": [{"to": "b"}, {"to": "d"}]},
             "d": {"name": "D", "adjacent": [{"to": "c"}]}}
    return {"rooms": rooms}


def test_a_leased_body_is_not_walked_on_by_the_window():
    bodies = {"tam": {"key": "tam", "place": "a", "available": True,
                      "leased": "present",
                      "walk": {"target": "c", "route": ["a", "b", "c"],
                               "leg": 0, "credit": 0.0, "held": False}}}
    moved, _travelled, _walked = continue_walks(bodies, 4.0, None)
    assert moved["tam"]["place"] == "a"


def test_an_errand_for_a_body_the_scene_stands_is_refused_by_name():
    charter = normalize_charter({
        "key": "inn", "upkeeps": {}, "posts": {}, "scene": _line(),
        "bodies": {"tam": {"place": "a", "leased": "present"}}})
    with pytest.raises(ValueError, match="scene"):
        send_errand(charter, body="tam", to="c", scene=_line())
    assert not charter["bodies"]["tam"].get("walk")


def test_a_body_that_arrives_and_is_reposted_spends_one_windows_credit():
    scene = _line()
    # A window that buys exactly one leg of this line, every leg alike.
    hours = edge_cost(scene, "a", "b") / WALK_ROOMS_PER_HOUR
    bodies = {"tam": {"key": "tam", "place": "a", "available": True,
                      "walk": {"target": "b", "route": ["a", "b"], "leg": 0,
                               "credit": 0.0, "held": False}}}
    walking, travelled, walked = continue_walks(bodies, hours, None,
                                                scene=scene)
    assert walking["tam"]["place"] == "b"
    posts = {"far": {"place": "d", "serves": [], "requires": {}}}
    after, travelled, _walked = relocate(walking, {"far": "tam"}, posts,
                                         scene, travelled, hours=hours,
                                         walked=walked)
    assert travelled.get("tam", 0) <= 1, travelled
