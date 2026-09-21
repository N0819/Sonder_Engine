"""One item is one RECORD; one item's rows may ACT ON several things.

THE CASE (the owner's chat 151, turn 7, 2026-09-20): "Both the doctor and
hinami steped into the tardis but the world never moved them into it."

Everything above the binder was right. The prose author gave the beat two
handles and kept them distinct across seven rows — `2: key`, `3: The TARDIS` —
and the objects hand minted a SEPARATE entity for the key and touched the ship
only for its lock and its doors:

    row [key, The Doctor]  ->  entities.tardis_key_1 = {name: key, description:
                               "A key fished from the pocket ..."}
                               inventory_ops[{object_id: tardis_key_1, held}]
    row [key]              ->  entities.the_tardis.state.hatch = "closed"
    row [The TARDIS]       ->  entities.the_tardis = {kind: ship, container,
                               interior_rooms, hatch: open}

`bind_items` then collapsed item 2 onto `the_tardis`. Item 2's two transforms
offered two candidates: the minted key, vouched for by the item's own NAME, and
the lock patch's bare `{"state": ...}`, admitted only by the singleton
`fallback`. With no standing `key` to anchor it, the tie went to whichever
candidate was already a world record — the ship — and the mint was aliased onto
it.

What that cost, all downstream and all correct given the corrupted record: the
Doctor was recorded HOLDING the TARDIS (`contained: {the_tardis: {in: "The
Doctor", mode: "held"}}`), the ship inherited the key's description and
`portable: true`, and when the next beat walked both bodies through the doors
the movement backstop refused it — you cannot walk into a thing somebody is
carrying — stripped both positions and said so twice.

The rule the fix states: a sibling transform's unnamed record does not decide
what an item IS. The fallback keeps its own job, which is an item no record
names at all.
"""

import json

import pytest

from world.causal_program import bind_items


KEY_DESC = "A key fished from the pocket of The Doctor's long brown coat."


def _rows():
    """Turn 7's three object transforms, as the hand actually emitted them."""
    return [
        {"item_id": 2, "chrono_id": 2, "object_name": "key",
         "patch": {"entities": {"tardis_key_1": {
                       "name": "key", "kind": "object", "portable": True,
                       "description": KEY_DESC}},
                   "inventory_ops": [{"op": "transfer",
                                      "object_id": "tardis_key_1",
                                      "from_id": "doctor", "to_id": "doctor",
                                      "relation": "held"}]}},
        {"item_id": 2, "chrono_id": 4, "object_name": "key",
         "patch": {"entities": {"the_tardis": {
                       "state": {"locked": False, "hatch": "closed"}}}}},
        {"item_id": 3, "chrono_id": 5, "object_name": "The TARDIS",
         "patch": {"entities": {"the_tardis": {
                       "kind": "ship", "container": True,
                       "state": {"hatch": "open"}}}}},
    ]


def _world(**over):
    """The ship standing on the beach; the key does not exist yet."""
    scene = {"entities": {"the_tardis": {"name": "The TARDIS", "kind": "object"}},
             "positions": {"the_tardis": "moonlit_beach"}}
    scene.update(over)
    return scene


class TestTheKeyIsNotTheShip:
    def test_the_mint_keeps_its_own_record(self):
        _bound, bindings, _notes = bind_items(_rows(), _world())
        assert bindings["2"]["entity"] == "tardis_key_1"
        assert bindings["3"]["entity"] == "the_tardis"

    def test_the_ship_does_not_inherit_the_key(self):
        """The failure as the owner met it: the police box wearing a key's
        description, carried in a coat pocket."""
        bound, _bindings, _notes = bind_items(_rows(), _world())
        ship = {}
        for row in bound:
            ship.update(((row.get("patch") or {}).get("entities") or {})
                        .get("the_tardis") or {})
        assert ship.get("description") != KEY_DESC
        assert ship.get("name") != "key"
        assert not ship.get("portable")

    def test_the_row_that_acts_on_the_lock_still_acts_on_the_lock(self):
        """The half that must NOT change: an item's rows may act on things the
        item is not. Turning a key in a lock patches the lock."""
        bound, _bindings, _notes = bind_items(_rows(), _world())
        lock = next(r for r in bound if r["chrono_id"] == 4)
        assert set(lock["patch"]["entities"]) == {"the_tardis"}
        assert lock["patch"]["entities"]["the_tardis"]["state"]["hatch"] == "closed"

    def test_the_transfer_moves_the_key_and_not_the_ship(self):
        bound, _bindings, _notes = bind_items(_rows(), _world())
        fish = next(r for r in bound if r["chrono_id"] == 2)
        assert fish["patch"]["inventory_ops"][0]["object_id"] == "tardis_key_1"

    def test_it_says_what_it_refused(self):
        """Reported, never silent: the next reader of this beat can see which
        record was kept out of the item's identity and why."""
        _bound, _bindings, notes = bind_items(_rows(), _world())
        assert any("does not decide what this item is" in str(n.get("reason"))
                   and "the_tardis" in (n.get("keys") or [])
                   for n in notes), notes


class TestAGuessThatNamesNothingStandingStillFolds:
    """The narrowing the suite demanded, kept as its own case.

    The first version of this fix dropped every fallback candidate wherever a
    named one existed, and broke the ordinary continuation:
    `test_causal_program.test_binding_happens_before_partial_entity_validation`
    has one item whose second transform patches the SAME thing with a bare
    `{"state": ...}` and no name. That guess captures nothing -- it resolves to
    no world record -- so it must still fold onto the item. Only a guess the
    world ALREADY HOLDS can capture the item, because that is what `held`
    prefers.
    """

    def test_two_terse_transforms_of_one_thing_both_land(self):
        rows = [
            {"item_id": 7, "chrono_id": 1, "object_name": "Brass Box",
             "patch": {"entities": {"first_key": {"name": "Brass Box",
                                                  "state": {"open": True}}}}},
            {"item_id": 7, "chrono_id": 2, "object_name": "Brass Box",
             "patch": {"entities": {"second_key": {"state": {"open": False}}}}},
        ]
        scene = {"entities": {"box": {"name": "Brass Box", "kind": "item"}},
                 "positions": {"box": "keeper_room"}}
        bound, bindings, _notes = bind_items(rows, scene)
        assert bindings["7"]["entity"] == "box"
        states = [((r.get("patch") or {}).get("entities") or {})
                  .get("box", {}).get("state", {}).get("open") for r in bound]
        assert states == [True, False]


class TestTheFallbackKeepsItsOwnJob:
    """It exists for an item NO record names, and that case is untouched."""

    def test_an_item_no_record_names_still_binds_through_the_fallback(self):
        rows = [{"item_id": 7, "chrono_id": 1, "object_name": "sluice gate",
                 "patch": {"entities": {"sluice_gate": {
                     "state": {"open": True}}}}}]
        scene = {"entities": {"sluice_gate": {"name": "sluice gate"}},
                 "positions": {"sluice_gate": "mill_race"}}
        _bound, bindings, _notes = bind_items(rows, scene)
        assert bindings["7"]["entity"] == "sluice_gate"

    def test_a_single_named_candidate_is_unaffected(self):
        rows = [{"item_id": 4, "chrono_id": 1, "object_name": "copper coin",
                 "patch": {"entities": {"copper_coin": {
                     "name": "copper coin", "kind": "coin"}}}}]
        _bound, bindings, _notes = bind_items(rows, {"entities": {}})
        assert bindings["4"]["entity"] == "copper_coin"

    def test_a_standing_record_the_name_vouches_for_still_wins(self):
        """A hand that mints a second spelling of a thing the world already
        holds is still folded onto the standing record -- that is the binder's
        actual job and the reason it exists."""
        rows = [{"item_id": 9, "chrono_id": 1, "object_name": "oak bar counter",
                 "patch": {"entities": {"counter_2": {
                     "name": "oak bar counter", "kind": "fixture"}}}}]
        scene = {"entities": {"oak_bar_counter": {"name": "oak bar counter"}},
                 "positions": {"oak_bar_counter": "taproom"}}
        _bound, bindings, _notes = bind_items(rows, scene)
        assert bindings["9"]["entity"] == "oak_bar_counter"

    @pytest.mark.parametrize("scene", [
        {"entities": {"the_tardis": {"name": "The TARDIS"},
                      "key": {"name": "key", "kind": "fixture"}},
         "positions": {"the_tardis": "moonlit_beach", "key": "moonlit_beach"}},
    ])
    def test_a_standing_key_still_anchors_the_item(self, scene):
        """With the key already a world record, the binder folded the mint onto
        it correctly even before this change. It still does."""
        _bound, bindings, _notes = bind_items(_rows(), scene)
        assert bindings["2"]["entity"] == "key"
        assert bindings["3"]["entity"] == "the_tardis"
