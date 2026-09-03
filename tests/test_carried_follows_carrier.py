"""A carried thing follows its carrier, including a carrier the scene does
not stand.

Harrowmere t5 (2026-09-02): the objects hand resolved a perfect transfer,
`sealed_letter` from `Wren Ashby` to `reeve_halinham`, `relation: held`.
The reeve is a Charter body -- the town stands him in the hall, the scene
has no entity and no position for him -- so `resolve_placement_target`
returned nothing, the op fell through with no note, and the letter stayed
in the player's containment record for the remaining thirty-five beats,
sleeping in her room at the inn. The scene now accepts a holder the town
vouches for (`carriers`), records who vouched, keeps the record through
hygiene, and reads the holder's room from the town on every later merge.
"""

from __future__ import annotations

import copy

from world.spatial import (
    carrier_lookup, containment_conceals, derive_contained_positions,
    derive_inventory_placements, merge_scene_with_diff,
    normalize_scene_containment, resolve_placement_target)


CARRIERS = {
    "Reeve halinham nookfeller": "reeve_hall",
    "Halinham Nookfeller": "reeve_hall",
    "post:reeve:0": "reeve_hall",
    "Clerk seleton orrholmeer": "clerk_office",
    "Seleton Orrholmeer": "clerk_office",
}


def _scene():
    return {
        "rooms": {
            "reeve_hall": {"name": "Reeve's Hall",
                           "adjacent": [{"to": "clerk_office"},
                                        {"to": "market_square"}]},
            "clerk_office": {"name": "Clerk's Office",
                             "adjacent": [{"to": "reeve_hall"}]},
            "market_square": {"name": "Market Square",
                              "adjacent": [{"to": "reeve_hall"}]},
        },
        "entities": {
            "sealed_letter": {"name": "sealed letter", "kind": "item",
                              "portable": True, "aliases": ["letter"]},
        },
        "positions": {"Wren Ashby": "reeve_hall", "sealed_letter": "reeve_hall"},
        "attire": {"Wren Ashby": {"regions": {}}},
        "contained": {"sealed_letter": {"in": "Wren Ashby", "mode": "held"}},
    }


HANDOVER = {"op": "transfer", "object_id": "sealed_letter",
            "from_id": "Wren Ashby", "to_id": "reeve_halinham",
            "relation": "held"}


class TestLookingUpAVouchedHolder:
    def test_exact_spelling_then_a_subset_of_one_bodys_words(self):
        assert carrier_lookup(CARRIERS, "post:reeve:0") == \
            ("post:reeve:0", "reeve_hall")
        assert carrier_lookup(CARRIERS, "reeve_halinham") == \
            ("Reeve halinham nookfeller", "reeve_hall")
        assert carrier_lookup(CARRIERS, "Nookfeller")[1] == "reeve_hall"
        assert carrier_lookup(CARRIERS, "orrholmeer")[1] == "clerk_office"

    def test_a_word_two_bodies_share_lands_on_neither(self):
        shared = dict(CARRIERS, **{"Clerk halinham vell": "clerk_office"})
        assert carrier_lookup(shared, "halinham") == (None, None)
        assert carrier_lookup(CARRIERS, "") == (None, None)
        assert carrier_lookup(None, "reeve") == (None, None)

    def test_the_scene_still_answers_first(self):
        scene = _scene()
        assert resolve_placement_target(scene, "reeve_hall", CARRIERS) == \
            ("room", "reeve_hall")
        assert resolve_placement_target(scene, "Wren Ashby", CARRIERS) == \
            ("carrier", "Wren Ashby")
        assert resolve_placement_target(scene, "reeve_halinham", CARRIERS) \
            == ("vouched", "Reeve halinham nookfeller")
        assert resolve_placement_target(scene, "reeve_halinham") == \
            (None, None)


class TestTheHandoverLands:
    def test_the_record_names_who_vouched_and_the_thing_stays_in_view(self):
        scene = _scene()
        report = []
        derive_inventory_placements(scene, [HANDOVER], report=report,
                                    carriers=CARRIERS)
        assert scene["contained"]["sealed_letter"] == {
            "in": "Reeve halinham nookfeller", "mode": "held",
            "by": "charter"}
        assert report == []
        assert not containment_conceals(scene, "Wren Ashby", "sealed_letter")

    def test_a_holder_the_scene_stands_itself_carries_no_vouching(self):
        scene = _scene()
        scene["positions"]["Mara"] = "reeve_hall"
        scene["attire"]["Mara"] = {"regions": {}}
        derive_inventory_placements(
            scene, [dict(HANDOVER, to_id="Mara")], carriers=CARRIERS)
        assert scene["contained"]["sealed_letter"] == {
            "in": "Mara", "mode": "held"}

    def test_nobody_vouching_is_said_out_loud_and_changes_nothing(self):
        scene = _scene()
        before = copy.deepcopy(scene)
        report = []
        derive_inventory_placements(scene, [HANDOVER], report=report)
        assert scene == before
        assert len(report) == 1
        assert "'reeve_halinham'" in report[0]
        assert "present" not in report[0] or "payload" in report[0]

    def test_hygiene_keeps_a_vouched_record_and_drops_an_unvouched_one(self):
        scene = _scene()
        scene["contained"] = {
            "sealed_letter": {"in": "Reeve halinham nookfeller",
                              "mode": "held", "by": "charter"},
            "coin": {"in": "somebody nobody stands", "mode": "pocket"},
        }
        scene["entities"]["coin"] = {"name": "coin", "kind": "item"}
        normalize_scene_containment(scene)
        assert set(scene["contained"]) == {"sealed_letter"}
        assert scene["contained"]["sealed_letter"]["by"] == "charter"


class TestTheThingFollows:
    def test_into_the_room_the_town_now_stands_the_holder_in(self):
        scene = _scene()
        scene["contained"] = {"sealed_letter": {
            "in": "Reeve halinham nookfeller", "mode": "held",
            "by": "charter"}}
        moved = {k: ("clerk_office" if v == "reeve_hall" else v)
                 for k, v in CARRIERS.items()}
        derive_contained_positions(scene, carriers=moved)
        assert scene["positions"]["sealed_letter"] == "clerk_office"

    def test_but_not_out_of_the_map_and_not_without_the_town(self):
        scene = _scene()
        scene["contained"] = {"sealed_letter": {
            "in": "Reeve halinham nookfeller", "mode": "held",
            "by": "charter"}}
        away = {k: "tithe_barn" for k in CARRIERS}
        derive_contained_positions(scene, carriers=away)
        assert scene["positions"]["sealed_letter"] == "reeve_hall"
        derive_contained_positions(scene)
        assert scene["positions"]["sealed_letter"] == "reeve_hall"

    def test_the_whole_merge_end_to_end_and_the_beats_after(self):
        landed = merge_scene_with_diff(
            _scene(), {"inventory_ops": [HANDOVER]}, carriers=CARRIERS)
        assert landed["contained"]["sealed_letter"]["in"] == \
            "Reeve halinham nookfeller"
        assert landed["positions"]["sealed_letter"] == "reeve_hall"

        # The player leaves; the reeve walks to the office. The letter is
        # the reeve's now and goes with him, not with her.
        moved = {k: ("clerk_office" if v == "reeve_hall" else v)
                 for k, v in CARRIERS.items()}
        later = merge_scene_with_diff(
            landed, {"positions": {"Wren Ashby": "market_square"}},
            carriers=moved)
        assert later["positions"]["sealed_letter"] == "clerk_office"
        assert later["positions"]["Wren Ashby"] == "market_square"

        # A merge that knows nothing of the town keeps the record and the
        # last room: stale, never handed back.
        bare = merge_scene_with_diff(later, {})
        assert bare["contained"]["sealed_letter"]["by"] == "charter"
        assert bare["positions"]["sealed_letter"] == "clerk_office"

    def test_a_story_with_no_town_merges_byte_identically(self):
        scene = _scene()
        with_none = merge_scene_with_diff(copy.deepcopy(scene), {})
        with_empty = merge_scene_with_diff(copy.deepcopy(scene), {},
                                           carriers={})
        assert with_none == with_empty
