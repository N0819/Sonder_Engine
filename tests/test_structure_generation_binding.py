"""A required room is bound, an authored resident survives, and a frontier
label asserts only what a label knows.

All four findings are one shape: an authored name that the engine had a place
for and did not put it in.

PM10 (multitude run turn 8, 2026-09-05). The Writers' Room asked for a
location with `required_rooms` naming the live yard and the three rooms it had
planted twenty minutes earlier. `_remap_generated_town` saw the id collision,
namespaced EVERY generated room -- the required ones included -- and planted
`vaunts_yard_waterfront_2_yard` beside the live `yard`, with eleven siblings
and all fourteen bodies inside them. `publish_package` then reported success
with `rooms: []`, because it read the result's `town` (the town's NAME, a
string) as a dict. The engine diagnosed itself three turns later, in a
`background_react` decision nobody reads: "9 charter places, 6 rooms in scope,
no id in common -- no body can ever surface here." The yard was empty for the
second half of the story.

PM12, the same failure in the person namespace. `featured_residents` is keyed
on `seed_id` by the closure, the request contract asks the model for
`{name, role}`, and a row without a seed was dropped in silence -- so Bram
Hardesty and Kester Prowse became Wulvenan Pintlewason and Tadferard
Balemaning.

PS8 (solitude run, 2026-09-05). A frontier label minted a planned room whose
whole description was its own name, behind a door onto an open dry lake bed.
"""

from __future__ import annotations

import time

import pytest

from world.charter_generate import (ensure_required_rooms,
                                    normalize_featured_residents,
                                    required_room_ids)
from world.charter_runtime import _remap_generated_town, _unreachable_institution
from world.structure import mint_frontier, plant_structure


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Yard", "A working waterfront.", time.time()))


def _town(rooms, charters=None):
    return {"name": "Vaunt's Yard Waterfront",
            "structure": {"key": "vaunts_yard_waterfront",
                          "name": "Vaunt's Yard Waterfront",
                          "max_planned": 40},
            "rooms": rooms, "charters": charters or {}}


# ---------------------------------------------------------------------------
# PM10 -- a required room is bound by id
# ---------------------------------------------------------------------------

class TestARequiredRoomIsBoundNotDuplicated:
    def test_a_collision_on_a_required_room_does_not_rename_it(self, temp_db):
        """A required room is named by ID, so its collision with an existing
        room is the point of asking for it, not an accident to route around.
        Everything the author did NOT name still takes the namespace."""
        cid = _chat(temp_db)
        plant_structure(cid, {"key": "yardside", "name": "Yardside"},
                        {"yard": {"name": "Yard"},
                         "bothy": {"name": "Bothy"}})
        town = _town({"yard": {"name": "Yard",
                               "adjacent": [{"to": "rope_walk"}]},
                      "rope_walk": {"name": "Rope Walk"},
                      "bothy": {"name": "Bothy"}},
                     {"yard_company": {"key": "yard_company",
                                       "bodies": {"a": {"place": "yard"}}}})
        out = _remap_generated_town(cid, town, {"items": {}},
                                    pinned=["yard", "rope_walk"])
        assert "yard" in out["rooms"], sorted(out["rooms"])
        assert "rope_walk" in out["rooms"]
        # `bothy` collided and was not required, so it moved.
        assert "bothy" not in out["rooms"]
        # And the body it placed followed the pin, not a copy.
        assert out["charters"]["yard_company"]["bodies"]["a"]["place"] == "yard"

    def test_with_nothing_pinned_the_namespace_rule_is_unchanged(self, temp_db):
        cid = _chat(temp_db)
        plant_structure(cid, {"key": "yardside", "name": "Yardside"},
                        {"yard": {"name": "Yard"}})
        out = _remap_generated_town(cid, _town({"yard": {"name": "Yard"}}),
                                    {"items": {}})
        assert "yard" not in out["rooms"]

    def test_required_room_ids_is_the_one_derivation(self):
        """The closure and the pin must agree about which id an entry names,
        or a room is minted under one spelling and bound under another."""
        assert required_room_ids([{"name": "Wharf Apron"}, "rope walk",
                                  {"id": "north_basin_slip"}]) == [
            "wharf_apron", "rope_walk", "north_basin_slip"]

    def test_connect_to_is_read_as_an_edge(self):
        """The charter planner's own request contract asks for `connect_to`;
        the closure read only `adjacent`, so every edge an author wrote was
        dropped and every required room hung off the first standing anchor."""
        town = _town({"wharf_apron": {"name": "Wharf Apron"}})
        ensure_required_rooms(town, [
            {"name": "rope_walk", "connect_to": "Wharf Apron"}])
        assert [e["to"] for e in town["rooms"]["rope_walk"]["adjacent"]] \
            == ["wharf_apron"]


class TestAnInstitutionOnGroundNobodyShares:
    """`no_shared_ground` is a FATAL condition for an institution, not a note
    a downstream stage files three turns later where nobody reads it."""

    REGISTRY = {"items": {"waterfront": {"state": {"bodies": {
        "a": {"place": "vaunts_yard_waterfront_2_yard",
              "berth": "vaunts_yard_waterfront_2_bothy"}}}}}}

    def test_an_institution_no_room_holds_is_a_warning(self):
        warnings = _unreachable_institution(
            self.REGISTRY, planted={"rope_walk"}, bound=set(),
            live_rooms={"yard", "wharf_apron"})
        assert warnings and "waterfront" in warnings[0]
        assert "surface" in warnings[0]

    def test_a_bound_room_is_shared_ground(self):
        registry = {"items": {"waterfront": {"state": {"bodies": {
            "a": {"place": "yard", "berth": "yard"}}}}}}
        assert _unreachable_institution(
            registry, planted={"rope_walk"}, bound={"yard"},
            live_rooms={"yard"}) == []

    def test_a_story_with_no_rooms_at_all_says_nothing(self):
        """There is nothing to be out of reach OF."""
        assert _unreachable_institution(
            self.REGISTRY, planted=set(), bound=set(), live_rooms=set()) == []


# ---------------------------------------------------------------------------
# PM12 -- the author's people, by name
# ---------------------------------------------------------------------------

class TestAFeaturedResidentSurvivesTheClosure:
    def test_a_name_alone_is_enough_to_be_identified_by(self):
        rows = normalize_featured_residents([
            {"name": "Bram Hardesty", "role": "Yard Gatekeeper"},
            {"name": "Kester Prowse", "role": "Crane Master"}])
        assert [r["name"] for r in rows] == ["Bram Hardesty", "Kester Prowse"]
        assert all(r["seed_id"] for r in rows)
        assert rows[0]["post"] == "Yard Gatekeeper"

    def test_the_same_person_asked_for_twice_is_one_person(self):
        rows = normalize_featured_residents([
            {"name": "Bram Hardesty"}, {"name": "bram  hardesty"}])
        assert len(rows) == 1

    def test_a_real_seed_is_never_overwritten(self):
        rows = normalize_featured_residents([
            {"name": "Bram Hardesty", "seed_id": "card:17"}])
        assert rows[0]["seed_id"] == "card:17"

    def test_a_row_naming_nobody_is_dropped(self):
        assert normalize_featured_residents([{"role": "gatekeeper"}, {}, ""]) == []

    def test_a_named_resident_reaches_the_closed_charter(self):
        """The whole point: the closure places them, under their own name."""
        from world.charter_generate import close_plan

        plan = {"charters": [{
            "key": "yard_company", "name": "Yard Company",
            "rooms": {"yard": {"name": "Yard", "purpose": "work"}},
            "upkeeps": {"gate": {"place": "yard", "span": "a_day"}},
            "posts": {"gatekeeper": {"place": "yard", "serves": ["gate"]}},
            "populations": [{"post": "gatekeeper", "count": 1,
                             "place": "yard"}],
        }], "rooms": {"yard": {"name": "Yard", "purpose": "work"}},
            "structure": {"key": "yardside", "name": "Yardside"}}
        residents = normalize_featured_residents([
            {"name": "Bram Hardesty", "role": "gatekeeper"}])
        town = close_plan(plan, featured_residents=residents)
        names = {str(b.get("name") or "")
                 for state in town["charters"].values()
                 for b in (state.get("bodies") or {}).values()}
        assert "Bram Hardesty" in names


# ---------------------------------------------------------------------------
# PS8 -- a frontier label asserts only what a label knows
# ---------------------------------------------------------------------------

class TestAFrontierLabelAssertsLittle:
    def test_no_purpose_that_merely_echoes_the_name(self):
        """A structure with no grammar falls back to a rule built out of the
        axis label, so the purpose came back as the room's own name: a place
        whose entire description is "Lake Sarrat Dry Bed". An absent purpose
        is honest; the Director furnishes the room on entry."""
        uid, spec = mint_frontier({"key": "shoreline", "max_planned": 20},
                                  "shoreline_wharf_pans",
                                  "Lake Sarrat Dry Bed", "1:s", [])
        assert uid == "lake_sarrat_dry_bed"
        assert spec["purpose"] == ""

    def test_the_edge_is_an_opening_and_not_a_door(self):
        """A label says what lies that way and nothing about what stands
        between -- and `open_door` outdoors is a door between a wharf terrace
        and a dry lake bed."""
        _uid, spec = mint_frontier({"key": "shoreline", "max_planned": 20},
                                   "shoreline_wharf_pans",
                                   "Lake Sarrat Dry Bed", "1:s", [])
        assert [e["barrier"] for e in spec["adjacent"]] == ["open"]

    def test_a_grammar_purpose_that_is_not_the_name_survives(self):
        """The rule is about an ECHO of the name, not about purposes: a
        grammar that says what a place is FOR still says it."""
        grammar = {"key": "harrowmere", "max_planned": 100, "grammar": [
            {"kind": "road", "names": ["upland road", "bridge road"],
             "purposes": ["approach", "crossing"]}]}
        _uid, spec = mint_frontier(grammar, "gate", "upland road", "1:h", [])
        assert spec["purpose"] in ("approach", "crossing")
