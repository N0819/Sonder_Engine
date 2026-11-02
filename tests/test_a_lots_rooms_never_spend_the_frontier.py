"""A building's rooms are inside it: they never spend the frontier's quota.

`structure.max_planned` is read two ways (audit 2026-11-01,
world_layout_bridge_structure F12): `plant_structure` checks one call's
rooms against it, and `prepare_frontier_expansion` checks the STRUCTURE'S
total. `agents.director_lots.expand_lot` plants up to 14 rooms a lot into
the lot's own part of the map, which the per-call check never stops, so a
village whose expanded lots took it past the cap (200 by default) retained
every frontier axis with no warning, and a walk to the village's edge minted
nothing -- the beat then invents the places. A lot's interior rooms (`lot_of`
naming another room: the lot's entry) are no places on the map's edge; the
lot itself counts once, as it did before it was expanded. The number is the
owner's and is unchanged.

Hand-made plans; the names are illustrations, not the rule.
"""
from __future__ import annotations

import time

from world.structure import plant_structure, prepare_frontier_expansion

VILLAGE = {"key": "village", "max_planned": 3, "grammar": []}


def test_a_lot_s_rooms_never_spend_the_frontier(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Village", "", time.time()))
    plant_structure(cid, VILLAGE, {
        "gate": {"name": "Village Gate", "purpose": "gate", "frontier": ["north road"],
                 "adjacent": [{"to": "store", "barrier": "closed_door"}]},
        "store": {"name": "General Store", "purpose": "the shop floor", "exposure": "enclosed",
                  "lot": {"expanded": 2}, "lot_of": "store",
                  "adjacent": [{"to": "gate", "barrier": "closed_door"},
                               {"to": "store__back", "barrier": "open_door"}]}})
    plant_structure(cid, VILLAGE, {
        "store__back": {"name": "Back Room", "purpose": "storage", "exposure": "enclosed",
                        "lot_of": "store", "adjacent": [{"to": "store__up", "vertical": "up"}]},
        "store__up": {"name": "Living Room", "purpose": "family", "exposure": "enclosed",
                      "level": 1, "lot_of": "store"}})
    scene = {"rooms": {"gate": {"name": "Village Gate", "adjacent": []}},
             "positions": {"Player": "gate"}}
    scene, _mutations = prepare_frontier_expansion(cid, scene)
    minted = [rid for rid, room in scene["rooms"].items()
              if rid not in ("gate", "store") and room.get("planned")]
    assert minted, "the north road is a place on the map's edge, and the store's rooms are inside"
