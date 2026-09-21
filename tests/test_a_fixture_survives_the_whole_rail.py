"""A fixture the plan names has to still be there when somebody stands in the room.

Every hop of this rail rebuilds a room as a dict literal naming the fields it
carries, and every such literal is a chance to drop one silently. It happened
FOUR TIMES on this one rail, to the same field, and each hop had its own
passing test:

  1. `structure.plant_structure` -- the plant's normalizer (fixed 2026-09-19)
  2. `charter_generate.close_plan` -- the closure's room rebuild
  3. `structure.skeleton_rooms` -- the opening's read-back
  4. `tools/two_lives_drive.seed_scene` -- the harness that stands bodies up

`plant_structure`'s own comment records the same shape swallowing the plan's
MEASUREMENTS once before (F47, measured in all five play runs of 2026-09-05).
Unit tests per hop cannot catch this: each hop was correct in isolation and the
field died in the gaps. Measured live (v10, 2026-09-20): 13 of 15 planned rooms
carried anchors in the registry and 0 of 15 did in the scene, and three rounds
of blaming the Writers' Room for not drafting fixtures went by before anybody
looked at the other end of the pipe.

So this test walks the rail. It is deliberately end-to-end and deliberately
about ONE field, because the field is not the point -- the gaps are.
"""

from __future__ import annotations

import time

from world.charter_generate import close_plan
from world.structure import plant_structure, skeleton_rooms

SHROUD = {"desc": "the wet timber shroud over the wheel"}
STRUCTURE = {"key": "aldermill", "max_planned": 8}


def _plan():
    """One room furnished by the AUTHOR, one furnished only by the DUTY that
    stands in it -- the two ways a fixture can enter a plan."""
    return {
        "name": "Aldermill",
        "structure": dict(STRUCTURE),
        "rooms": {"mill_race": {"name": "Mill Race", "purpose": "work",
                                "anchors": {"shroud": dict(SHROUD)}},
                  "mill_house": {"name": "The Mill", "purpose": "work"}},
        "charters": [{"key": "mill", "name": "Aldermill Mill",
                      "posts": {"head_miller": {"place": "mill_house",
                                                "anchor": "millstones"}},
                      "populations": [{"post": "head_miller", "count": 1}]}],
    }


def test_a_fixture_survives_every_hop_from_plan_to_scene(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("T", "", time.time()))

    # HOP 1 -- the closure. Both sources must be present after it: the
    # author's own anchor, and one seeded from the post that stands at it.
    closed = close_plan(_plan())
    rooms = closed["rooms"]
    assert rooms["mill_race"]["anchors"]["shroud"]["desc"] == SHROUD["desc"]
    assert "millstones" in rooms["mill_house"]["anchors"]

    # HOP 2 -- the plant.
    plant_structure(cid, closed["structure"], rooms)

    # HOP 3 -- the read-back the opening composes its scene from.
    skeleton = skeleton_rooms(cid, STRUCTURE["key"])["rooms"]
    assert skeleton["mill_race"]["anchors"]["shroud"]["desc"] == SHROUD["desc"]
    assert "millstones" in skeleton["mill_house"]["anchors"]

    # HOP 4 -- and the hand that resolves a contact target can name them,
    # which is the only reason any of this matters.
    from agents.director import _anchor_names

    sc = {"rooms": skeleton, "positions": {"Emory Vane": "mill_race"},
          "entities": {}}
    assert _anchor_names(sc, ["Emory Vane"])["mill_race"]["shroud"] \
        == SHROUD["desc"]


def test_the_harness_that_stands_bodies_up_carries_them_too(temp_db):
    """The fourth allowlist was in `tools/`, not in the engine, and a rail
    that ends in a scene nobody is standing in is not a rail."""
    import inspect

    from tools import two_lives_drive

    src = inspect.getsource(two_lives_drive.seed_scene)
    assert "anchors" in src, (
        "seed_scene builds each room as a dict literal; a field it does not "
        "name is a field the scene does not get")
