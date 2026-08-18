"""See-through barriers, and containers as places.

Barriers answered one question — can a body pass — and every consumer reused
that answer for sight as well. So there was no way to say "you can see it and
cannot reach it". A window had to degrade to `wall` (the normalizer's fallback
for anything it does not recognize, so opaque) or be lied about as `open`. That
is an oversight for ordinary rooms long before it is one for containers: a cell
with a barred door, an observation port, a shopfront.

`window` and `bars` fill it, and the three questions are now kept apart:

    passage   open, open_door
    sight     open, open_door, window, bars
    ambient   open, open_door, bars          (glass stops sound; bars do not)

Which is also what makes a sealed glass container work without any special
case: the occupant is in the container's interior room, the derived doorway is
a window, and `has_visual` — the single place sight is decided — says they and
the room can see each other but not reach.

And the other half: an interior attached to something being CARRIED is not part
of the surrounding room's view. Without that, a character stood in a hall
perpetually perceived the inside of their own bag.
"""

from __future__ import annotations

import pytest

from world.spatial import (
    _SIGHT_BARRIERS,
    _PASSABLE_BARRIERS,
    _AMBIENT_BARRIERS,
    _SCENT_BARRIER_LEVELS,
    has_visual,
    merge_scene_with_diff,
    normalize_barrier,
    scent_level,
    spatial_rel,
    visible_adjacent_rooms,
)


class TestTheVocabulary:
    @pytest.mark.parametrize("raw", [
        "window", "glass", "glass_door", "pane", "porthole", "viewport",
        "observation_window", "transparent", "sealed_glass", "GLASS WALL",
    ])
    def test_glassy_things_normalize_to_window(self, raw):
        assert normalize_barrier(raw) == "window"

    @pytest.mark.parametrize("raw", [
        "bars", "barred", "barred_door", "cage", "grate", "grille",
        "portcullis", "lattice", "mesh",
    ])
    def test_barred_things_normalize_to_bars(self, raw):
        assert normalize_barrier(raw) == "bars"

    def test_they_used_to_fall_through_to_opaque_wall(self):
        """The old behaviour for anything unrecognized, which is what made this
        an oversight rather than a missing nicety."""
        assert normalize_barrier("nonsense_barrier") == "wall"

    def test_the_three_questions_are_distinct(self):
        assert "window" in _SIGHT_BARRIERS
        assert "window" not in _PASSABLE_BARRIERS
        assert "window" not in _AMBIENT_BARRIERS

        assert "bars" in _SIGHT_BARRIERS
        assert "bars" not in _PASSABLE_BARRIERS
        assert "bars" in _AMBIENT_BARRIERS      # sound carries through a cage

    def test_the_fourth_question_is_graded_and_scent_level_reads_it(
            self, monkeypatch):
        """Scent is not a yes/no like its three siblings -- a closed door and a
        curtain both pass it, weakened -- so its vocabulary is a table, and
        `scent_level` must be that table's only reader.

        It was not. The set existed, was documented in AGENTS.md as gating
        scent "the same way `_SIGHT_BARRIERS` gates sight", was asserted on by
        a test, and decided nothing: `scent_level` restated the same rule as
        literal tuples in its own body. Two statements of one rule, free to
        disagree, with a test guarding the one that did not run.
        """
        assert _SCENT_BARRIER_LEVELS["open"] == "full"
        assert _SCENT_BARRIER_LEVELS["closed_door"] == "muffled"
        assert "window" not in _SCENT_BARRIER_LEVELS  # glass stops air
        assert "wall" not in _SCENT_BARRIER_LEVELS

        # The guard that the constant is load-bearing: move the rule and the
        # function moves with it.
        monkeypatch.setitem(_SCENT_BARRIER_LEVELS, "open", "muffled")
        assert scent_level({"barrier": "open"}) == "muffled"
        monkeypatch.delitem(_SCENT_BARRIER_LEVELS, "bars")
        assert scent_level({"barrier": "bars"}) == "none"


class TestSightThroughBarriers:
    def _two_rooms(self, barrier):
        return {
            "rooms": {
                "cell": {"name": "Cell", "desc": "A cell.", "adjacent": [
                    {"to": "corridor", "barrier": barrier, "distance": "near"}]},
                "corridor": {"name": "Corridor", "desc": "A corridor.", "adjacent": []},
            },
            "positions": {"Prisoner": "cell", "Guard": "corridor"},
            "entities": {},
        }

    @pytest.mark.parametrize("barrier,visible", [
        ("open", True), ("open_door", True),
        ("window", True), ("bars", True),
        ("closed_door", False), ("wall", False),
    ])
    def test_has_visual(self, barrier, visible):
        scene = self._two_rooms(barrier)
        rel = spatial_rel(scene, "cell", "corridor")
        assert has_visual(rel) is visible

    def test_sight_is_mutual(self):
        scene = self._two_rooms("window")
        assert has_visual(spatial_rel(scene, "cell", "corridor"))
        assert has_visual(spatial_rel(scene, "corridor", "cell"))

    def test_a_window_is_not_a_way_through(self):
        scene = self._two_rooms("window")
        assert spatial_rel(scene, "cell", "corridor")["barrier"] == "window"
        assert "window" not in _PASSABLE_BARRIERS

    def test_an_adjacent_room_seen_through_glass_is_listed(self):
        scene = self._two_rooms("window")
        seen = visible_adjacent_rooms(scene, "cell")
        assert [r["room_id"] for r in seen] == ["corridor"]
        assert seen[0]["barrier"] == "window"

    def test_a_closed_door_still_hides_the_room(self):
        scene = self._two_rooms("closed_door")
        assert visible_adjacent_rooms(scene, "cell") == []


class TestSealedInGlass:
    """A container big enough to be inside is a room; `enclosure` says what a
    closed one still lets through."""

    def _jar(self, enclosure, hatch="closed"):
        return {
            "rooms": {
                "hall": {"name": "Hall", "desc": "A hall.", "adjacent": []},
                "jar_inside": {"name": "Inside the jar", "desc": "Curved glass.", "adjacent": [],
                               "parent_entity": "jar"},
            },
            "positions": {"Hinami": "jar_inside", "Tamamo": "hall",
                          "jar": "hall"},
            "entities": {"jar": {
                "name": "Glass Jar", "kind": "object",
                "enclosure": enclosure,
                "interior_rooms": ["jar_inside"],
                "state": {"hatch": hatch},
            }},
        }

    def test_a_sealed_glass_container_is_seen_into(self):
        scene = merge_scene_with_diff(self._jar("transparent"), {})
        rel = spatial_rel(scene, "hall", "jar_inside")

        assert rel["barrier"] == "window"
        assert has_visual(rel) is True

    def test_the_occupant_can_see_out(self):
        scene = merge_scene_with_diff(self._jar("transparent"), {})
        assert has_visual(spatial_rel(scene, "jar_inside", "hall")) is True

    def test_but_cannot_get_out(self):
        scene = merge_scene_with_diff(self._jar("transparent"), {})
        rel = spatial_rel(scene, "jar_inside", "hall")
        assert rel["barrier"] not in _PASSABLE_BARRIERS

    def test_an_opaque_container_hides_its_occupant(self):
        scene = merge_scene_with_diff(self._jar("opaque"), {})
        assert has_visual(spatial_rel(scene, "hall", "jar_inside")) is False

    def test_opaque_is_the_default(self):
        scene = self._jar("transparent")
        scene["entities"]["jar"].pop("enclosure")
        scene = merge_scene_with_diff(scene, {})
        assert spatial_rel(scene, "hall", "jar_inside")["barrier"] == "closed_door"

    def test_a_cage_carries_sound_as_well_as_sight(self):
        scene = merge_scene_with_diff(self._jar("barred"), {})
        rel = spatial_rel(scene, "hall", "jar_inside")

        assert rel["barrier"] == "bars"
        assert has_visual(rel) is True
        assert rel["barrier"] in _AMBIENT_BARRIERS

    def test_opening_it_makes_a_real_doorway(self):
        scene = merge_scene_with_diff(self._jar("transparent", hatch="open"), {})
        rel = spatial_rel(scene, "jar_inside", "hall")

        assert rel["barrier"] == "open_door"
        assert rel["barrier"] in _PASSABLE_BARRIERS


class TestCarriedInteriorsAreNotScenery:
    """An interior attached to something being carried is not part of the
    surrounding room's view. Keyed on the carrier relation, not on smallness."""

    def _bag(self, **over):
        scene = {
            "rooms": {
                "hall": {"name": "Hall", "desc": "A hall.", "adjacent": []},
                "bag_inside": {"name": "Inside the bag", "desc": "Dark canvas.", "adjacent": [],
                               "parent_entity": "bag"},
            },
            "positions": {"Tamamo": "hall", "bag": "hall"},
            "entities": {"bag": {
                "name": "Satchel", "kind": "object", "portable": True,
                "interior_rooms": ["bag_inside"],
                "state": {"hatch": "open"},
            }},
            "contained": {}, "contacts": [], "scales": {},
        }
        scene.update(over)
        return scene

    def test_the_owner_does_not_perpetually_see_inside_it(self):
        scene = merge_scene_with_diff(self._bag(), {})
        seen = [r["room_id"] for r in visible_adjacent_rooms(scene, "hall")]
        assert "bag_inside" not in seen

    def test_it_applies_to_anything_being_carried_not_just_small_things(self):
        """Keyed on the carrier relation: a crate nobody is carrying stays
        visible; the same crate once picked up does not."""
        scene = self._bag()
        scene["entities"]["bag"].pop("portable")
        loose = merge_scene_with_diff(scene, {})
        assert "bag_inside" in [r["room_id"]
                                for r in visible_adjacent_rooms(loose, "hall")]

        carried = merge_scene_with_diff(
            scene, {"containment": {"bag": {"in": "Tamamo", "mode": "carried"}}})
        assert "bag_inside" not in [r["room_id"]
                                    for r in visible_adjacent_rooms(carried, "hall")]

    def test_a_ship_you_walk_through_stays_visible(self):
        """Nobody is carrying the ship, so its hold is ordinary scenery."""
        scene = {
            "rooms": {
                "dock": {"name": "Dock", "desc": "A dock.", "adjacent": [
                    {"to": "hold", "barrier": "open", "distance": "near"}]},
                "hold": {"name": "Cargo Hold", "desc": "A hold.", "adjacent": [],
                         "parent_entity": "ship"},
            },
            "positions": {"ship": "dock"},
            "entities": {"ship": {"name": "Ship", "kind": "vehicle",
                                  "interior_rooms": ["hold"]}},
        }
        assert "hold" in [r["room_id"] for r in visible_adjacent_rooms(scene, "dock")]

    def test_being_inside_it_still_shows_the_way_out(self):
        """Suppression is about looking IN, never about looking out."""
        scene = merge_scene_with_diff(self._bag(), {})
        assert "hall" in [r["room_id"]
                          for r in visible_adjacent_rooms(scene, "bag_inside")]

    def test_an_occupant_of_a_carried_glass_jar_is_still_seen(self):
        """The split that matters: you do not take in the inside of a carried
        thing as a PLACE, but a body visible through its wall is still a body
        you can see."""
        scene = merge_scene_with_diff({
            "rooms": {
                "hall": {"name": "Hall", "desc": "A hall.", "adjacent": []},
                "jar_inside": {"name": "Inside the jar", "desc": "Curved glass.", "adjacent": [],
                               "parent_entity": "jar"},
            },
            "positions": {"Hinami": "jar_inside", "Tamamo": "hall",
                          "jar": "hall"},
            "entities": {"jar": {
                "name": "Jar", "kind": "object", "portable": True,
                "enclosure": "transparent",
                "interior_rooms": ["jar_inside"],
                "state": {"hatch": "closed"}}},
            "contained": {"jar": {"in": "Tamamo", "mode": "carried"}},
            "contacts": [], "scales": {},
        }, {})

        assert has_visual(spatial_rel(scene, "hall", "jar_inside")) is True
        assert "jar_inside" not in [r["room_id"]
                                    for r in visible_adjacent_rooms(scene, "hall")]


class TestNothingElseChanged:
    def test_ordinary_rooms_are_unaffected(self):
        scene = {
            "rooms": {
                "a": {"name": "A", "desc": "Room A.", "adjacent": [
                    {"to": "b", "barrier": "open", "distance": "near"}]},
                "b": {"name": "B", "desc": "Room B.", "adjacent": []},
            },
            "positions": {}, "entities": {},
        }
        assert [r["room_id"] for r in visible_adjacent_rooms(scene, "a")] == ["b"]

    def test_a_room_with_no_parent_entity_is_never_suppressed(self):
        from world.spatial import _is_carried_interior

        scene = {"rooms": {"a": {"name": "A"}}, "entities": {}}
        assert _is_carried_interior(scene, "a") is False

    def test_a_missing_room_is_not_a_carried_interior(self):
        from world.spatial import _is_carried_interior

        assert _is_carried_interior({"rooms": {}}, "nope") is False
