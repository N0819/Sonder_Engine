"""A planned edge declared from one side is a doorway from both.

The Charter Planner declared the Stair's steps from the Stair's side only
(scratch play 2026-09-14, chat 7): the landed scene put the creature one room
below the player and no edge led back down to it, so nothing it did could
reach her, the aperture never held it, and the Director minted a "cliff" for
the steps she was looking down. `plant_structure` settles the reciprocal edge
with the same barrier; a room may still declare its own side differently.
"""

import time

from world.structure import plant_structure, registry_rows


def test_the_other_side_of_a_declared_doorway_is_planted(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Two sides", "", time.time()))
    plant_structure(cid, {"key": "cove", "max_planned": 6, "grammar": []}, {
        "the_stair": {"name": "The Stair", "purpose": "steps", "frontier": [],
                      "adjacent": [{"to": "headland_lane", "barrier": "open_door"}]},
        "headland_lane": {"name": "Headland Lane", "purpose": "track", "frontier": [],
                          "adjacent": [{"to": "chapel", "barrier": "open_door"}]},
        "chapel": {"name": "Chapel", "purpose": "bell", "frontier": [],
                   "adjacent": [{"to": "headland_lane", "barrier": "closed_door"}]},
    })
    rows = registry_rows(cid)
    lane = {e["to"]: e.get("barrier") for e in rows["headland_lane"]["planned"]["adjacent"]}
    assert lane["the_stair"] == "open_door"
    # A side a room declared for itself is kept as declared.
    assert lane["chapel"] == "open_door"
    chapel = {e["to"]: e.get("barrier") for e in rows["chapel"]["planned"]["adjacent"]}
    assert chapel == {"headland_lane": "closed_door"}
