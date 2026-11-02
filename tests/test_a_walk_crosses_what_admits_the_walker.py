"""A walk crosses a link that admits the walker, on the same graph
`passable_route_exists(body=)` already answers.

Audit world_spatial_movement_sight F7 (2026-11-01, CONFIRMED WRONG-SCENE): a
closed admitting link derives `{barrier: wall, admits: [...]}`
(`spatial_transit._link_edge`). On the shrine's Seal shape
`passable_route_exists(cavern, realm, body='Amaterasu')` was True, but
`passable_path` was `[]`, `passable_route_next_step` None and `walk` None --
two answers to one question on two graphs. In `director_movement` that means
a declared walk teleported with no cell, a follower skipped, and a continuing
walk held "no passable route" every beat.
"""

from world.spatial import (apply_transit_dock_edges, passable_path,
                           passable_route_exists, passable_route_next_step,
                           walk)


def _scene():
    sc = {
        "rooms": {
            "cavern": {"name": "Cavern", "desc": "Steam.", "adjacent": [], "zone": "shrine"},
            "realm": {"name": "Realm", "desc": "Light.", "adjacent": [], "zone": "realm"},
        },
        "entities": {"seal": {"name": "The Seal", "kind": "portal",
                              "state": {"link": {"rooms": ["cavern", "realm"],
                                                 "phase": "closed",
                                                 "admits": ["goddess"]}}}},
        "positions": {"Goddess": "realm", "Raider": "cavern"},
    }
    apply_transit_dock_edges(sc)
    return sc


def test_the_admitted_body_has_a_path_and_a_next_step():
    sc = _scene()
    assert passable_route_exists(sc, "realm", "cavern", body="Goddess")
    assert passable_path(sc, "realm", "cavern", body="Goddess") == ["cavern"]
    assert passable_route_next_step(sc, "realm", "cavern", body="Goddess") == "cavern"


def test_the_admitted_body_walks_through_and_a_stranger_does_not():
    sc = _scene()
    went = walk(sc, "Goddess", "cavern", paces=40)
    assert went is not None and went["room"] == "cavern"
    assert walk(sc, "Raider", "realm", paces=40) is None


def test_with_no_body_named_the_link_is_still_a_wall():
    sc = _scene()
    assert passable_path(sc, "realm", "cavern") == []
    assert passable_route_next_step(sc, "realm", "cavern") is None
