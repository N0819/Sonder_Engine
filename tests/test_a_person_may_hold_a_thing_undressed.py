"""A body's standing must not depend on its wardrobe.

`resolve_placement_target` sorts a transfer's destination into a room, a
CARRIER (a body -- the thing goes with them) or an ANCHOR (a thing the scene
places -- it sits at that thing). Body-ness was derived from `attire` and
`scales` alone, on the stated ground that `kind` is free text a model writes.
True of a model's word, and the engine writes one of its own:
`agents/common.mint_cast_entities` mints `kind: "person"` for every cast
member and the player, from the positions table, under the sheet's own
spelling -- "a cast member is a body whether or not the opening wrote one".

Ignoring that record made an unclothed character a room fixture. Measured live
(`google/gemini-3.8-flash`, the Millbrook run, 2026-09-17): a courier was
handed a letter and the ferry fare, the Director emitted both transfers
correctly, and both landed on the floor --

    possession: 'letter' reached 'char_lysa_fen''s room, but its exact
    placement needs a station naming a room anchor.

-- so she spent the night waiting for payment she was holding, and crossed the
water without the letter she was sent with. Her reasoning was right the whole
time; the world model was wrong.
"""
from __future__ import annotations

import copy

from world.spatial import derive_inventory_placements, resolve_placement_target


def _scene(**over):
    """A courier and a traveller, and not one garment between them."""
    scene = {
        "rooms": {"tap_room": {"name": "Tap room", "adjacent": []}},
        "positions": {"Aleth": "tap_room", "Lysa Fen": "tap_room",
                      "letter": "tap_room"},
        "entities": {
            "char_aleth": {"name": "Aleth", "kind": "person", "aliases": []},
            "char_lysa_fen": {"name": "Lysa Fen", "kind": "person",
                              "aliases": []},
            "letter": {"name": "letter", "kind": "letter", "portable": True},
        },
        "attire": {}, "scales": {}, "contained": {},
    }
    scene.update(over)
    return scene


def _hand_over(scene, to_id="Lysa Fen"):
    report = []
    derive_inventory_placements(scene, [{
        "op": "transfer", "object_id": "letter", "from_id": "Aleth",
        "to_id": to_id, "relation": "held"}], report=report)
    return report


class TestAnUndressedPersonIsStillABody:
    def test_she_resolves_as_a_carrier_with_an_empty_wardrobe(self):
        scene = _scene()
        assert scene["attire"] == {}, "the whole point"
        assert resolve_placement_target(scene, "Lysa Fen") == (
            "carrier", "char_lysa_fen")

    def test_the_thing_ends_up_in_her_hand(self):
        scene = _scene()
        report = _hand_over(scene)
        assert scene["contained"]["letter"] == {
            "in": "char_lysa_fen", "mode": "held"}
        assert report == [], report

    def test_one_garment_never_mattered_and_still_does_not(self):
        """The paired case, so a fix that simply always answered `carrier`
        cannot pass this file: clothed or not, the same answer."""
        dressed = _scene(attire={"Lysa Fen": {"torso": [{"item": "coat"}]}})
        _hand_over(dressed)
        assert dressed["contained"]["letter"]["in"] == "char_lysa_fen"

    def test_a_thing_is_still_a_thing(self):
        """The distinction the widening must not erase. A table is where you
        SET something down -- it gets a station in the table's own room --
        and it is not a body that carries it around."""
        scene = _scene()
        scene["entities"]["trestle"] = {"name": "trestle table",
                                        "kind": "furniture"}
        scene["positions"]["trestle"] = "tap_room"
        assert resolve_placement_target(scene, "trestle") == ("anchor", "trestle")

    def test_a_room_is_still_a_room(self):
        scene = _scene()
        assert resolve_placement_target(scene, "tap_room") == (
            "room", "tap_room")

    def test_a_destination_nobody_vouches_for_is_still_refused(self):
        scene = _scene()
        assert resolve_placement_target(scene, "the harbourmaster") == (
            None, None)
        before = copy.deepcopy(scene)
        _hand_over(scene, to_id="the harbourmaster")
        assert scene["contained"] == before["contained"]
