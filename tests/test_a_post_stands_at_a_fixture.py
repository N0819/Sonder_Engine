"""A duty is stood at a fixture, so that fixture is in the room.

The charter contract has always told the planner that a post may carry
`anchor` -- "the id of one of its place's fixtures -- where in the room the
duty is stood, as one of that room's anchors" -- and the planner has always
obeyed it. Measured on a fresh Aldermill (2026-09-20): 13 of 13 posts across
four institutions named one -- `millstones`, `sluice_gate`, `oak_bar`,
`baking_hearth`, `bellows_lever`, `reeve_bench`, `shoeing_stall`.

Not one of them existed as a room anchor. The contract referenced a set that
nothing asked anybody to create and nothing read back, so `spatial_contacts`
could not resolve a hand laid on any of them, and a mill was a room name with
a sentence of prose.

That is also why three separate attempts to ask the Room for `anchors`
directly came back 0 of 19, 0 of 12 and 0 of 19 rooms furnished. It had named
the fixtures already, in the other field, and had no reason to say them twice.
The Room was not the thing that was broken.

Two holes on one rail, both closed here: `close_plan`'s room rebuild is an
allowlist that dropped a plan's own `anchors` (the same shape that had already
swallowed the plan's measurements, F47, and its fixtures in `plant_structure`),
and nothing turned a post's anchor into the fixture it stands at.
"""

from __future__ import annotations

from world.charter_generate import close_plan

MILL = {"key": "mill", "name": "Aldermill Mill",
        "posts": {"head_miller": {"place": "mill_house", "anchor": "millstones"},
                  "mill_hand": {"place": "mill_house", "anchor": "flour_bin"}},
        "populations": [{"post": "head_miller", "count": 1}]}


def _plan(rooms=None, charters=None):
    return {"name": "Aldermill",
            "structure": {"key": "aldermill", "max_planned": 8},
            "rooms": rooms if rooms is not None
            else {"mill_house": {"name": "The Mill", "purpose": "work"}},
            "charters": charters if charters is not None else [MILL]}


class TestTheDutyFurnishesItsRoom:
    def test_each_post_anchor_becomes_a_room_fixture(self):
        rooms = close_plan(_plan())["rooms"]
        assert sorted(rooms["mill_house"]["anchors"]) == ["flour_bin",
                                                          "millstones"]

    def test_a_fixture_follows_its_post_to_where_the_post_ends_up(self):
        """A post naming a place the plan does not hold is REASSIGNED by the
        closure -- a duty has to be stood somewhere real. The fixture follows
        it, because the fixture is where the duty is stood and the closure has
        just decided where that is. Asserted rather than assumed: the first
        version of this test expected the fixture to be dropped, and the
        engine was right."""
        charter = {**MILL, "posts": {"warden": {"place": "elsewhere",
                                                "anchor": "gate"}}}
        out = close_plan(_plan(charters=[charter]))
        landed = out["charters"]["mill"]["posts"]["warden"]["place"]
        assert landed == "mill_house"
        assert "gate" in out["rooms"][landed]["anchors"]

    def test_a_post_that_stands_anywhere_names_no_fixture(self):
        """The contract says to omit `anchor` where the duty is stood
        anywhere in the room, and an omission must furnish nothing."""
        charter = {**MILL, "posts": {"sweeper": {"place": "mill_house"}}}
        rooms = close_plan(_plan(charters=[charter]))["rooms"]
        assert "anchors" not in rooms["mill_house"]


class TestThePlansOwnFixturesSurvive:
    def test_an_authored_anchor_is_carried_through_the_rebuild(self):
        rooms = close_plan(_plan(rooms={
            "mill_house": {"name": "The Mill",
                           "anchors": {"hearth": {"desc": "a wide stone hearth"}}}},
            charters=[]))["rooms"]
        assert rooms["mill_house"]["anchors"]["hearth"]["desc"] \
            == "a wide stone hearth"

    def test_a_described_fixture_outranks_a_derived_one(self):
        """An explicit description is the author's; a post anchor only
        guarantees the fixture EXISTS. The description must win."""
        charter = {**MILL, "posts": {"head_miller": {"place": "mill_house",
                                                     "anchor": "millstones"}}}
        rooms = close_plan(_plan(rooms={
            "mill_house": {"name": "The Mill",
                           "anchors": {"millstones": {"desc": "two great stones"}}}},
            charters=[charter]))["rooms"]
        assert rooms["mill_house"]["anchors"]["millstones"]["desc"] \
            == "two great stones"

    def test_a_room_nobody_works_in_stays_unfurnished(self):
        """No invention: a fixture is created from a duty, never guessed."""
        rooms = close_plan(_plan(rooms={
            "mill_house": {"name": "The Mill"},
            "lane": {"name": "River Lane"}}))["rooms"]
        assert "anchors" not in rooms["lane"]
