"""Containment: being carried, pocketed, jarred, or ridden along.

The sibling of scale, and the reason it exists. A body shrunk to a tenth and
picked up is not merely "in contact with" the hand holding it — it has stopped
being an independently positioned thing. Contact alone left the tiny person
free to walk out of the room while sitting in someone's pocket, because nothing
tied their position to their container's.

So the load-bearing property here is that **a contained body's position is
derived**, transitively, every merge. Getting out is an explicit release the
Director declares, never a side effect of writing a position — "they climbed
out and walked away" and "the Director forgot they were in a pocket" produce
the identical diff, and only one of them is meant.

Interior rooms remain the mechanism for large containers you stand INSIDE (a
ship, a building). This is the other direction: a container that carries you.
"""

from __future__ import annotations

import pytest

from spatial import (
    containment_broken_by_scale_change,
    carrier_chain,
    containment_facts,
    container_of,
    contents_of,
    derive_contained_positions,
    merge_scene_with_diff,
    normalize_scene_containment,
    spatial_facts,
)


def _scene(**over):
    scene = {
        "rooms": {"hall": {"name": "Hall", "adjacent": []},
                  "yard": {"name": "Yard", "adjacent": []}},
        "positions": {"Hinami": "hall", "Tamamo": "hall"},
        "entities": {}, "contacts": [], "scales": {}, "contained": {},
    }
    scene.update(over)
    return scene


def _pocketed():
    return {"containment": {"Hinami": {"in": "Tamamo", "mode": "pocket"}}}


class TestBeingCarried:
    def test_it_is_recorded(self):
        scene = merge_scene_with_diff(_scene(), _pocketed())
        assert container_of(scene, "Hinami") == "Tamamo"
        assert contents_of(scene, "Tamamo") == ["Hinami"]

    def test_a_bare_string_is_accepted(self):
        scene = merge_scene_with_diff(
            _scene(), {"containment": {"Hinami": "Tamamo"}})
        assert container_of(scene, "Hinami") == "Tamamo"

    def test_releasing_sets_them_down(self):
        scene = merge_scene_with_diff(_scene(), _pocketed())
        scene = merge_scene_with_diff(scene, {"containment": {"Hinami": None}})

        assert container_of(scene, "Hinami") is None
        assert scene["contained"] == {}

    def test_nobody_can_carry_themselves(self):
        scene = merge_scene_with_diff(
            _scene(), {"containment": {"Hinami": {"in": "Hinami"}}})
        assert scene["contained"] == {}

    def test_a_scene_that_never_carries_anyone_is_unchanged(self):
        scene = merge_scene_with_diff(_scene(), {})
        assert scene["contained"] == {}


class TestPositionIsDerived:
    """The whole point: a carried body does not have its own position."""

    def test_the_carried_body_moves_with_its_carrier(self):
        scene = merge_scene_with_diff(_scene(), _pocketed())
        scene = merge_scene_with_diff(scene, {"positions": {"Tamamo": "yard"}})

        assert scene["positions"]["Hinami"] == "yard"

    def test_a_carried_body_cannot_walk_off_on_its_own(self):
        """Writing a position for someone in a pocket is overwritten. This is
        the bug containment exists to prevent."""
        scene = merge_scene_with_diff(_scene(), _pocketed())
        scene = merge_scene_with_diff(scene, {"positions": {"Hinami": "yard"}})

        assert scene["positions"]["Hinami"] == "hall"   # still in the pocket
        assert scene["positions"]["Tamamo"] == "hall"

    def test_releasing_first_lets_them_move(self):
        scene = merge_scene_with_diff(_scene(), _pocketed())
        scene = merge_scene_with_diff(scene, {
            "containment": {"Hinami": None},
            "positions": {"Hinami": "yard"},
        })
        assert scene["positions"]["Hinami"] == "yard"

    def test_a_chain_follows_the_outermost_carrier(self):
        """A person in a jar in a satchel goes where the satchel goes."""
        scene = merge_scene_with_diff(_scene(
            positions={"Hinami": "hall", "Tamamo": "hall",
                       "Jar": "hall", "Satchel": "hall"},
        ), {"containment": {
            "Hinami": {"in": "Jar", "mode": "container"},
            "Jar": {"in": "Satchel", "mode": "container"},
            "Satchel": {"in": "Tamamo", "mode": "carried"},
        }})
        scene = merge_scene_with_diff(scene, {"positions": {"Tamamo": "yard"}})

        assert scene["positions"]["Hinami"] == "yard"
        assert scene["positions"]["Jar"] == "yard"
        assert carrier_chain(scene, "Hinami") == ["Jar", "Satchel", "Tamamo"]

    def test_derivation_does_not_mint_a_second_spelling_of_a_name(self):
        scene = _scene(positions={"hinami": "hall", "Tamamo": "yard"},
                       contained={"Hinami": {"in": "Tamamo", "mode": "pocket"}})
        derive_contained_positions(scene)

        # The key already in positions is reused; two spellings would put one
        # person in two rooms, the bug the entity dedup exists to prevent.
        assert scene["positions"] == {"hinami": "yard", "Tamamo": "yard"}

    def test_a_carrier_with_no_position_leaves_them_where_they_were(self):
        scene = _scene(contained={"Hinami": {"in": "Ghost", "mode": "held"}},
                       entities={"Ghost": {"name": "Ghost"}})
        derive_contained_positions(scene)
        assert scene["positions"]["Hinami"] == "hall"


class TestCycles:
    def test_a_direct_cycle_is_refused(self):
        scene = merge_scene_with_diff(_scene(), {"containment": {
            "Hinami": {"in": "Tamamo"}, "Tamamo": {"in": "Hinami"}}})

        # One of them must give; what matters is that derivation terminates.
        assert len(scene["contained"]) < 2

    def test_a_longer_cycle_is_refused(self):
        scene = merge_scene_with_diff(_scene(
            positions={"A": "hall", "B": "hall", "C": "hall"},
        ), {"containment": {
            "A": {"in": "B"}, "B": {"in": "C"}, "C": {"in": "A"}}})

        assert len(scene["contained"]) < 3

    def test_the_chain_walker_is_cycle_safe(self):
        scene = _scene(contained={"A": {"in": "B"}, "B": {"in": "A"}})
        assert carrier_chain(scene, "A") == ["B"]


class TestHygiene:
    def test_a_container_the_scene_does_not_know_is_dropped(self):
        scene = merge_scene_with_diff(
            _scene(), {"containment": {"Hinami": {"in": "Nowhere"}}})
        assert scene["contained"] == {}

    def test_an_entity_container_without_a_position_is_kept(self):
        """A jar is a legitimate container even before anyone puts it down."""
        scene = merge_scene_with_diff(_scene(
            entities={"Jar": {"name": "Jar", "kind": "object"}},
        ), {"containment": {"Hinami": {"in": "Jar", "mode": "container"}}})

        assert container_of(scene, "Hinami") == "Jar"

    def test_a_malformed_value_is_normalized(self):
        scene = _scene(contained="not a dict")
        assert normalize_scene_containment(scene)["contained"] == {}

    def test_junk_records_are_dropped(self):
        scene = merge_scene_with_diff(_scene(), {"containment": {
            "Hinami": {"in": ""}, "": {"in": "Tamamo"}, "X": 7}})
        assert scene["contained"] == {}

    def test_the_table_is_bounded(self):
        from spatial import _MAX_CONTAINED

        positions = {"Tamamo": "hall"}
        containment = {}
        for i in range(_MAX_CONTAINED + 15):
            positions[f"P{i}"] = "hall"
            containment[f"P{i}"] = {"in": "Tamamo", "mode": "carried"}
        scene = merge_scene_with_diff(
            _scene(positions=positions), {"containment": containment})
        assert len(scene["contained"]) == _MAX_CONTAINED

    def test_mode_defaults_rather_than_failing(self):
        scene = merge_scene_with_diff(
            _scene(), {"containment": {"Hinami": {"in": "Tamamo"}}})
        assert scene["contained"]["Hinami"]["mode"] == "carried"


class TestSizeReleasesContainment:
    """The interaction with scale: someone restored to full height is not still
    in the coat pocket."""

    def test_growing_back_gets_them_out(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.05}})
        scene = merge_scene_with_diff(scene, _pocketed())
        assert container_of(scene, "Hinami") == "Tamamo"

        scene = merge_scene_with_diff(scene, {"scales": {"Hinami": 1}})
        assert container_of(scene, "Hinami") is None

    def test_the_carrier_changing_size_releases_them_too(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.05}})
        scene = merge_scene_with_diff(scene, _pocketed())

        scene = merge_scene_with_diff(scene, {"scales": {"Tamamo": 0.05}})
        assert container_of(scene, "Hinami") is None

    def test_a_trivial_size_change_keeps_them_carried(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.05}})
        scene = merge_scene_with_diff(scene, _pocketed())

        scene = merge_scene_with_diff(scene, {"scales": {"Hinami": 0.055}})
        assert container_of(scene, "Hinami") == "Tamamo"

    def test_the_director_can_re_declare_in_the_same_beat(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.05}})
        scene = merge_scene_with_diff(scene, _pocketed())

        scene = merge_scene_with_diff(scene, {
            "scales": {"Hinami": 0.3},
            "containment": {"Hinami": {"in": "Tamamo", "mode": "held"}},
        })
        # Still carried, but as the thing it now is.
        assert container_of(scene, "Hinami") == "Tamamo"
        assert scene["contained"]["Hinami"]["mode"] == "held"

    def test_it_reports_who_was_released(self):
        scene = _scene(contained={"Hinami": {"in": "Tamamo", "mode": "pocket"}},
                       scales={"Hinami": 1.0})
        released = containment_broken_by_scale_change(scene, {"Hinami": 0.05})

        assert released == ["Hinami"]
        assert scene["contained"] == {}

    def test_a_released_body_is_not_dragged_along_that_same_beat(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.05}})
        scene = merge_scene_with_diff(scene, _pocketed())
        scene = merge_scene_with_diff(scene, {
            "scales": {"Hinami": 1},
            "positions": {"Tamamo": "yard"},
        })

        # Released first, so Tamamo's move does not carry her along.
        assert scene["positions"]["Hinami"] == "hall"
        assert scene["positions"]["Tamamo"] == "yard"


class TestGroundTruth:
    def test_the_carried_body_is_told_it_cannot_leave(self):
        scene = merge_scene_with_diff(_scene(), _pocketed())
        facts = " ".join(containment_facts(scene, "Hinami", ["Tamamo"]))

        assert "pocket" in facts
        assert "cannot leave on your own" in facts

    def test_the_carrier_is_told_what_it_is_carrying(self):
        scene = merge_scene_with_diff(_scene(), _pocketed())
        facts = " ".join(containment_facts(scene, "Tamamo", ["Hinami"]))
        assert "Hinami is pocket by you." in facts or "Hinami is" in facts

    def test_a_third_party_in_view_sees_the_arrangement(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Hinami": "hall", "Tamamo": "hall", "Bramwell": "hall"},
        ), _pocketed())
        facts = " ".join(containment_facts(scene, "Bramwell", ["Tamamo", "Hinami"]))
        assert "Hinami" in facts and "Tamamo" in facts

    def test_nothing_is_said_when_nobody_is_carried(self):
        scene = merge_scene_with_diff(_scene(), {})
        assert containment_facts(scene, "Hinami", ["Tamamo"]) == []

    def test_it_reaches_the_narrator_ground_truth(self):
        scene = merge_scene_with_diff(_scene(), _pocketed())
        facts = spatial_facts(scene, "Hinami", ["Tamamo"])
        assert any("cannot leave on your own" in f for f in facts)


class TestSchema:
    def test_containment_survives_state_diff_validation(self):
        from schemas import StateDiff

        diff = StateDiff(containment={"Hinami": {"in": "Tamamo",
                                                 "mode": "pocket"}})
        assert diff.dict()["containment"]["Hinami"]["in"] == "Tamamo"

    def test_a_null_release_survives_validation(self):
        from schemas import StateDiff

        assert StateDiff(containment={"Hinami": None}).dict()["containment"] \
            == {"Hinami": None}

    def test_the_director_shape_normalizer_accepts_it(self):
        from agents.director import _normalize_diff_shape

        assert _normalize_diff_shape({"containment": "junk"})["containment"] == {}
