"""A room created this turn must be reachable from somewhere.

Adjacency resolves BOTH ways, so a room with an empty `adjacent` is fine as
long as something points AT it. The failure is the stronger one: a room that no
edge reaches in EITHER direction. `spatial_rel` then answers `separated`/`far`
for every pair involving it, and its occupants can perceive nothing but each
other.

Live, chat 58 "Run! ⎇10 ⎇20". `northern_plaza` was minted with `adjacent: []`
and nothing pointing at it. The player stepped out of the TARDIS into a plaza
whose own description carried shuttered buildings, dripping awnings and the
alley a Dalek was grinding out of — and her view could offer her only the police
box she had just left, because the derived dock edge was the single edge the map
admitted. She looked around a city and was shown a doorway.

Applied only to rooms NEW in this merge, and only as they are created, because
that is the one moment the engine still has the context to place them: where the
bodies were standing immediately before. After the fact there is nothing left to
infer from.
"""

from __future__ import annotations

import pytest

from spatial import connect_orphan_new_rooms, merge_scene_with_diff, spatial_rel


PREV = {
    "rooms": {
        "street": {"name": "Street", "adjacent": []},
        "alley": {"name": "Alley",
                  "adjacent": [{"to": "street", "barrier": "open",
                                "distance": "near"}]},
    },
    "positions": {"Hinami": "street", "The Doctor": "street"},
    "entities": {},
}


def _merged(diff):
    return merge_scene_with_diff(PREV, diff)


def test_the_live_failure_a_new_island_is_connected():
    sc = _merged({"rooms": {"plaza": {"name": "Plaza", "adjacent": []}}})
    rel = spatial_rel(sc, "plaza", "street")
    assert rel["barrier"] != "separated", "the new room is an island"


def test_it_attaches_where_the_bodies_were():
    sc = _merged({"rooms": {"plaza": {"name": "Plaza", "adjacent": []}}})
    edges = {e["to"] for e in sc["rooms"]["plaza"]["adjacent"]}
    assert edges == {"street"}     # both bodies stood there before the merge


def test_a_new_room_that_declares_its_own_edge_is_left_alone():
    sc = _merged({"rooms": {"plaza": {
        "name": "Plaza",
        "adjacent": [{"to": "alley", "barrier": "open", "distance": "near"}]}}})
    edges = [e["to"] for e in sc["rooms"]["plaza"]["adjacent"]]
    assert edges == ["alley"]


def test_a_new_room_something_else_points_at_is_left_alone():
    """Edges resolve both ways — being POINTED AT is reachability. This is why
    `alley_room` was always fine with an empty `adjacent` of its own."""
    sc = _merged({"rooms": {
        "plaza": {"name": "Plaza", "adjacent": []},
        "street": {"name": "Street",
                   "adjacent": [{"to": "plaza", "barrier": "open",
                                 "distance": "near"}]},
    }})
    assert sc["rooms"]["plaza"]["adjacent"] == []
    assert spatial_rel(sc, "plaza", "street")["barrier"] != "separated"


def test_an_existing_orphan_is_not_retro_attached():
    """Only rooms NEW in this merge. An established map is never rewired — the
    context that would justify a guess is long gone."""
    prev = {**PREV, "rooms": {**PREV["rooms"],
                              "island": {"name": "Island", "adjacent": []}}}
    sc = merge_scene_with_diff(prev, {})
    assert sc["rooms"]["island"]["adjacent"] == []


def test_an_interior_is_never_touched():
    """A `parent_entity` room's doorway is DERIVED by apply_transit_dock_edges,
    and a sealed hull is severed from the world on purpose."""
    sc = _merged({
        "rooms": {"hold": {"name": "Hold", "parent_entity": "ship",
                           "adjacent": []}},
        "entities": {"ship": {"name": "A ship", "interior_rooms": ["hold"],
                              "state": {"transit": {"phase": "in_transit",
                                                    "hatch": "closed"}}}},
    })
    assert sc["rooms"]["hold"]["adjacent"] == []


def test_the_helper_reports_what_it_attached():
    scene = {"rooms": {"street": {"name": "Street", "adjacent": []},
                       "plaza": {"name": "Plaza", "adjacent": []}},
             "positions": {}}
    attached = connect_orphan_new_rooms(scene, {"rooms": {"street": {}},
                                                "positions": {}})
    assert attached == [("plaza", "street")]


def test_a_lone_room_is_a_noop():
    scene = {"rooms": {"plaza": {"name": "Plaza", "adjacent": []}},
             "positions": {}}
    assert connect_orphan_new_rooms(scene, {"rooms": {}, "positions": {}}) == []
