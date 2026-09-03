"""Where a carried thing is, is its carrier's -- through every door the
fact arrives by.

Harrowmere replay (2026-09-03), the baseline's gap 12 still open after the
vouched-carrier fix of the day before. Two doors were still shut:

* The player's SATCHEL was a worn garment in her attire ledger AND a scene
  entity minted as a container (so the letter could sit in it), with a
  position of its own that nothing tied to her. It stayed at the reeve's
  hall from t3 to t26 while she slept at the inn and walked the town.
  `derive_worn_containment` now ties a worn garment entity to its wearer
  every merge.
* At t5 the handover reached the merge as a CONTAINMENT record from the
  contact hand -- the reeve "takes hold of sealed letter" -- naming a body
  the scene had no entity for, and `normalize_scene_containment` dropped
  it as unknown. The op path had been taught to vouch such a holder; this
  door had not. It now keeps the record marked ``by: "charter"`` when the
  town stands the holder.
"""

from __future__ import annotations

import copy

from world.spatial import (
    derive_worn_containment, merge_scene_with_diff,
    normalize_scene_containment)


CARRIERS = {
    "Reeve of Harrowmere Brgaron Brfordwick": "reeve_hall",
    "Brgaron Brfordwick": "reeve_hall",
    "reeve:0001": "reeve_hall",
}

WREN = "Wren Ashby"


def _attire(*garments):
    return {
        "wearing": list(garments), "state": [],
        "regions": {"torso": {"garments": [
            {"name": g, "attaches": False, "description": "",
             "state": "worn", "condition": "", "covers": []}
            for g in garments], "beneath": ""}},
    }


def _scene():
    return {
        "rooms": {
            "upland_gate": {"name": "Upland Gate",
                            "adjacent": [{"to": "market_square"}]},
            "market_square": {"name": "Market Square",
                              "adjacent": [{"to": "upland_gate"},
                                           {"to": "reeve_hall"}]},
            "reeve_hall": {"name": "Reeve's Hall",
                           "adjacent": [{"to": "market_square"},
                                        {"to": "clerk_office"}]},
            "clerk_office": {"name": "Clerk's Office",
                             "adjacent": [{"to": "reeve_hall"}]},
        },
        "entities": {
            "canvas_satchel": {"name": "canvas satchel", "kind": "container",
                               "portable": True, "container": True,
                               "aliases": ["satchel", "bag"],
                               "enclosure": "opaque"},
            "sealed_letter": {"name": "sealed letter", "kind": "object",
                              "portable": True, "aliases": ["letter"]},
        },
        "positions": {WREN: "upland_gate", "canvas_satchel": "upland_gate",
                      "sealed_letter": "upland_gate"},
        "attire": {WREN: _attire("grey wool travelling dress",
                                 "canvas satchel")},
        "contained": {"sealed_letter": {"in": "canvas_satchel",
                                        "mode": "container"}},
    }


class TestAWornThingIsTiedToItsWearer:
    def test_the_wardrobe_ledger_writes_the_carriage_and_marks_it(self):
        scene = _scene()
        derive_worn_containment(scene)
        assert scene["contained"]["canvas_satchel"] == {
            "in": WREN, "mode": "worn", "by": "attire"}
        # A garment the scene holds no entity for is not a record.
        assert "grey wool travelling dress" not in scene["contained"]

    def test_the_satchel_and_the_letter_in_it_follow_her_across_town(self):
        scene = _scene()
        moved = merge_scene_with_diff(scene, {"positions": {WREN: "reeve_hall"}})
        assert moved["positions"]["canvas_satchel"] == "reeve_hall"
        assert moved["positions"]["sealed_letter"] == "reeve_hall"
        # The measured beats: she leaves for the inn, then walks the town.
        later = merge_scene_with_diff(
            moved, {"positions": {WREN: "market_square"}})
        assert later["positions"]["canvas_satchel"] == "market_square"
        assert later["positions"]["sealed_letter"] == "market_square"

    def test_a_declared_carriage_by_somebody_else_outranks_the_wardrobe(self):
        scene = _scene()
        scene["positions"]["Mara"] = "upland_gate"
        scene["attire"]["Mara"] = {"regions": {}}
        scene["contained"]["canvas_satchel"] = {"in": "Mara", "mode": "held"}
        derive_worn_containment(scene)
        assert scene["contained"]["canvas_satchel"] == {
            "in": "Mara", "mode": "held"}

    def test_a_shed_garment_stays_where_it_was_dropped(self):
        scene = _scene()
        derive_worn_containment(scene)
        merged = merge_scene_with_diff(scene, {"positions": {WREN: "reeve_hall"}})
        assert merged["positions"]["canvas_satchel"] == "reeve_hall"
        # Off it comes: the wardrobe no longer lists it. The derived record
        # retires; the satchel keeps the room it was set down in.
        merged["attire"][WREN] = _attire("grey wool travelling dress")
        after = merge_scene_with_diff(
            merged, {"positions": {WREN: "market_square"}})
        assert "canvas_satchel" not in after["contained"]
        assert after["positions"]["canvas_satchel"] == "reeve_hall"
        assert after["positions"][WREN] == "market_square"

    def test_a_worn_record_a_hand_wrote_is_not_the_wardrobes_to_retire(self):
        scene = _scene()
        scene["attire"][WREN] = _attire("grey wool travelling dress")
        scene["contained"]["canvas_satchel"] = {"in": WREN, "mode": "worn"}
        derive_worn_containment(scene)
        assert scene["contained"]["canvas_satchel"] == {
            "in": WREN, "mode": "worn"}

    def test_a_wearer_is_never_a_garment_and_a_voice_is_never_carried(self):
        scene = _scene()
        scene["entities"]["Wren Ashby"] = {"name": "Wren Ashby",
                                           "kind": "person"}
        scene["attire"]["Mara"] = _attire("Wren Ashby")
        scene["positions"]["Mara"] = "upland_gate"
        scene["entities"]["narrator_voice"] = {"name": "the voice",
                                               "kind": "voice",
                                               "ubiquitous": True}
        scene["attire"][WREN]["wearing"].append("the voice")
        derive_worn_containment(scene)
        assert "Wren Ashby" not in scene["contained"]
        assert "narrator_voice" not in scene["contained"]

    def test_a_story_with_no_wardrobe_is_byte_identical(self):
        scene = _scene()
        scene.pop("attire")
        scene["contained"] = {}
        before = copy.deepcopy(scene)
        derive_worn_containment(scene)
        assert scene == before


class TestAHandoverRecordedByTheContactHand:
    def test_hygiene_keeps_a_record_the_town_vouches_for(self):
        scene = _scene()
        scene["positions"][WREN] = "reeve_hall"
        scene["contained"] = {"sealed_letter": {
            "in": "Reeve of Harrowmere Brgaron Brfordwick", "mode": "held"}}
        dropped = copy.deepcopy(scene)
        normalize_scene_containment(dropped)
        assert "sealed_letter" not in dropped["contained"], \
            "the pre-fix behaviour: an unknown holder loses the record"
        normalize_scene_containment(scene, carriers=CARRIERS)
        assert scene["contained"]["sealed_letter"] == {
            "in": "Reeve of Harrowmere Brgaron Brfordwick", "mode": "held",
            "by": "charter"}

    def test_the_t5_beat_end_to_end_and_the_reeve_walks_off_with_it(self):
        scene = _scene()
        scene["positions"][WREN] = "reeve_hall"
        derive_worn_containment(scene)
        landed = merge_scene_with_diff(
            scene, {"containment": {"sealed_letter": {
                "in": "Reeve of Harrowmere Brgaron Brfordwick",
                "mode": "held"}}},
            carriers=CARRIERS)
        assert landed["contained"]["sealed_letter"]["by"] == "charter"
        assert landed["positions"]["sealed_letter"] == "reeve_hall"
        # She goes to the inn; he goes to the office. Her satchel goes with
        # her; his letter goes with him.
        moved = {k: "clerk_office" for k in CARRIERS}
        later = merge_scene_with_diff(
            landed, {"positions": {WREN: "market_square"}}, carriers=moved)
        assert later["positions"]["canvas_satchel"] == "market_square"
        assert later["positions"]["sealed_letter"] == "clerk_office"

    def test_a_holder_nobody_stands_is_still_dropped(self):
        scene = _scene()
        scene["contained"] = {"sealed_letter": {
            "in": "somebody nobody stands", "mode": "held"}}
        normalize_scene_containment(scene, carriers=CARRIERS)
        assert "sealed_letter" not in scene["contained"]
