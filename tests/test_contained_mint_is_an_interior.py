"""A room the engine routed to as an INSIDE is marked as one.

`mapping.classify_movement` answers `contained` for a destination that is an
entity or an entity's inside, and `agents/mapping.py` says what is supposed to
follow: "the spatial hand mints the room with `parent_entity`". Measured live
(chat 114 turn 10) it did not. The compiler classified `tardis_console_room`
contained, the spatial specialist minted a fully furnished room for it -- vast,
coral-pillared, `light: lit` -- and nothing wrote the parentage. Two things
followed, both silent:

  * `spatial_transit.apply_transit_dock_edges` indexes interiors by `parent_entity`
    alone, so the console room's doorway could never follow its holder. The
    box can fly anywhere and its doors still open onto the same sand.
  * the room was authored `exposure: "sheltered"`, which the weather reaches,
    so at 1am `room_light` darkened its declared `lit` to `dark`. The inside
    of a lamplit time machine read as pitch black because a free-text field
    said the rain could half-reach it.

The parentage is stamped from THIS TURN'S OWN CLASSIFICATION, never from a
structural sweep over every scene on disk: `entities[eid].interior_rooms` is
deliberately NOT filled here, because that index gates a Director specialist
and makes rooms un-prunable at commit, and widening it is its own landing with
its own two readers to test (docs/UNBUILT.md).

Database-independent: pure predicate, merge and exposure contracts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.mapping import (classify_movement, contained_interior_holder,
                            is_contained_destination)
from world.spatial import merge_scene_with_diff, room_light
from world.weather import room_exposure


def _scene():
    return {
        "rooms": {"beach": {"name": "Shore", "light": "lit",
                            "exposure": "open", "adjacent": []}},
        "entities": {"tardis": {"name": "The TARDIS", "kind": "vehicle",
                                "container": True, "interior_rooms": []}},
        "positions": {}, "stations": {},
    }


class TestWhichEntityAnInsideBelongsTo:
    def test_an_entity_prefixed_room_names_its_holder(self):
        assert contained_interior_holder(
            "tardis_console_room", _scene()) == "tardis"

    def test_a_listed_interior_names_its_holder(self):
        sc = _scene()
        sc["entities"]["tardis"]["interior_rooms"] = ["console"]
        assert contained_interior_holder("console", sc) == "tardis"

    def test_a_room_already_parented_keeps_its_holder(self):
        sc = _scene()
        sc["rooms"]["console"] = {"name": "Console", "parent_entity": "tardis"}
        assert contained_interior_holder("console", sc) == "tardis"

    def test_the_entity_itself_is_not_a_place_inside_anything(self):
        """A body is not a room and has no parentage to stamp -- but the
        ROUTING answer is unchanged, which is the contract this refactor
        must not break."""
        assert contained_interior_holder("tardis", _scene()) == ""
        assert contained_interior_holder("The TARDIS", _scene()) == ""
        assert is_contained_destination("tardis", _scene()) is True
        assert is_contained_destination("The TARDIS", _scene()) is True

    def test_an_ordinary_room_belongs_to_nobody(self):
        assert contained_interior_holder("harbour_office", _scene()) == ""
        assert is_contained_destination("harbour_office", _scene()) is False

    def test_the_routing_classification_still_says_contained(self):
        got = classify_movement(
            {"movement": {"to_room": "tardis_console_room"}}, _scene(),
            planned_for=lambda _q: None)
        assert got == {"to_room": "tardis_console_room", "status": "contained"}


class TestAnInsideIsEnclosedWhateverTheFieldSays:
    """Structural, not descriptive: the weather cannot reach inside a thing,
    so there is nothing for an author to be right about."""

    def test_parentage_outranks_a_declared_exposure(self):
        sc = _scene()
        sc["rooms"]["console"] = {"name": "Console", "exposure": "sheltered",
                                  "parent_entity": "tardis", "light": "lit"}
        assert room_exposure(sc, "console") == "enclosed"

    def test_the_night_sky_no_longer_darkens_a_lit_interior(self):
        sc = _scene()
        sc["day_phase"] = "night"
        sc["weather"] = {"sky": "clear"}
        sc["rooms"]["console"] = {"name": "Console", "exposure": "sheltered",
                                  "light": "lit"}
        assert room_light(sc, "console") == "dark"
        sc["rooms"]["console"]["parent_entity"] = "tardis"
        assert room_light(sc, "console") == "lit"

    def test_an_ordinary_sheltered_room_is_unchanged(self):
        sc = _scene()
        sc["rooms"]["porch"] = {"name": "Porch", "exposure": "sheltered"}
        assert room_exposure(sc, "porch") == "sheltered"


class TestTheParentageSurvivesTheMerge:
    def test_a_stamped_mint_commits_with_its_holder(self):
        diff = {"rooms": {"tardis_console_room": {
            "name": "Console Room", "light": "lit", "parent_entity": "tardis",
            "adjacent": [{"to": "beach", "barrier": "open_door"}]}}}
        merged = merge_scene_with_diff(_scene(), diff)
        assert merged["rooms"]["tardis_console_room"]["parent_entity"] \
            == "tardis"

    def test_the_holder_indexes_the_room_it_now_owns(self):
        """`parent_entity` and `entities[eid].interior_rooms` are one fact
        written twice, and `sync_entity_interior_rooms` derives the second
        from the first for every holder since 2026-09-04. Stamping the first
        without the second would have left the TARDIS an interior to half the
        engine and not to the other half."""
        diff = {"rooms": {"tardis_console_room": {
            "name": "Console Room", "parent_entity": "tardis",
            "adjacent": [{"to": "beach", "barrier": "open_door"}]}}}
        merged = merge_scene_with_diff(_scene(), diff)
        assert merged["entities"]["tardis"]["interior_rooms"] \
            == ["tardis_console_room"]
