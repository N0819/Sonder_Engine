"""A plan keeps where a place is and how far (2026-10-05).

The far layer (`world/landscape.py`) can only place a far room by the
compass its ways out carry and the metres they measure. A planned edge lost
both on the way in: its compass sat in `bearing`, which nothing reads (43
planned edges in the owner's registry carried one, and none could be
placed), and "40 m" was folded to `far` and the number thrown away.
"""

from __future__ import annotations

from story.plot_packages import _plan_edge
from world.charter_move import edge_seconds


def test_a_measurement_is_kept_and_a_word_still_folds():
    assert _plan_edge({"to": "x", "distance": "40 m"})["distance"] == "40 m"
    assert _plan_edge({"to": "x", "distance": "short"})["distance"] == "adjacent"
    assert _plan_edge({"to": "x", "distance": "far"})["distance"] == "far"


def test_a_bearing_is_a_dir_and_up_is_still_not_a_bearing():
    assert _plan_edge({"to": "x", "bearing": "north"}) == {"to": "x", "dir": "n"}
    assert _plan_edge({"to": "x", "bearing": "n", "dir": "e"}) == {"to": "x", "dir": "e"}
    assert _plan_edge({"to": "x", "bearing": "up"}) == {"to": "x", "vertical": "up"}
    out = _plan_edge({"to": "x", "bearing": "sw", "vertical": "down"})
    assert out == {"to": "x", "vertical": "down", "dir": "sw"}


def test_a_measured_crossing_costs_what_it_measures():
    sc = {"rooms": {"a": {"name": "a", "extent": {"w": 10, "d": 10},
                          "adjacent": [{"to": "b", "distance": "40 m"}]},
                    "b": {"name": "b"}}}
    measured = edge_seconds(sc, "a", "b")
    sc["rooms"]["a"]["adjacent"][0]["distance"] = "far"
    assert measured < edge_seconds(sc, "a", "b")
    sc["rooms"]["a"]["adjacent"][0]["distance"] = None
    assert measured > edge_seconds(sc, "a", "b")      # was read as no word at all
