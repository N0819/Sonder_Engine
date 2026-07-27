"""Scale: shrinking and growing, and what stops being possible afterwards.

A size change is live physical state, so it lives in the scene blob beside
positions and contacts rather than in a condition row -- the things that must
react to it (what can be reached, lifted, held, or gripped at all) are
scene-level questions, and one place for it is what stops two accounts drifting.

The property that matters most here is the one the engine can enforce
deterministically: **a hold is a fact about two bodies at the sizes they were.**
Shrink the held person to a tenth and "his hand grips her wrist" is not a
smaller version of itself -- the wrist is no longer where the hand is. So the
engine cancels rather than rescales, and the Director re-establishes whatever
the new geometry actually permits. Same discipline as movement: a contact the
physical situation no longer supports does not survive on inertia.

Everything else about feasibility is reported, not enforced. The Director owns
whether an act succeeds; `size_relation` only gives it geometry to reason from,
so "too small to reach the latch" comes from a number rather than from vibes.
"""

from __future__ import annotations

import pytest

from spatial import (
    clamp_scale,
    contacts_broken_by_scale_change,
    merge_scene_with_diff,
    normalize_scene_scales,
    scale_of,
    scale_ratio,
    size_facts,
    size_relation,
    size_tier,
    spatial_facts,
)


def _scene(**over):
    scene = {
        "rooms": {"hall": {"name": "Hall", "adjacent": []},
                  "yard": {"name": "Yard", "adjacent": []}},
        "positions": {"Hinami": "hall", "Tamamo": "hall"},
        "entities": {}, "contacts": [], "scales": {},
    }
    scene.update(over)
    return scene


def _held():
    return {"op": "add", "actor": "Tamamo", "actor_part": "hand",
            "target": "Hinami", "target_part": "wrist", "manner": "grip"}


class TestRecordingSize:
    def test_a_shrink_is_recorded(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.1}})
        assert scene["scales"]["Hinami"] == 0.1
        assert scale_of(scene, "Hinami") == 0.1

    def test_a_growth_is_recorded(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Tamamo": 8}})
        assert scale_of(scene, "Tamamo") == 8.0

    def test_an_unmentioned_body_is_normal_size(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.1}})
        assert scale_of(scene, "Tamamo") == 1.0

    def test_a_scene_that_never_mentions_size_behaves_as_before(self):
        scene = merge_scene_with_diff(_scene(), {})
        assert scene["scales"] == {}
        assert scale_of(scene, "Hinami") == 1.0

    def test_returning_to_normal_leaves_no_residue(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.1}})
        scene = merge_scene_with_diff(scene, {"scales": {"Hinami": 1}})

        # "Back to normal" is 1.0, and it is dropped rather than stored, so a
        # later reader cannot trip over a baseline entry.
        assert scene["scales"] == {}
        assert scale_of(scene, "Hinami") == 1.0

    def test_size_survives_stepping_offscreen(self):
        """Unlike a contact, a size does not require being in a room. Dropping
        the entry when someone leaves would silently restore them."""
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.1}})
        scene["positions"].pop("Hinami")
        scene = merge_scene_with_diff(scene, {})

        assert scale_of(scene, "Hinami") == 0.1

    def test_it_applies_to_anything_with_a_position(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Hinami": "hall", "The TARDIS": "hall"},
        ), {"scales": {"The TARDIS": 0.02}})
        assert scale_of(scene, "The TARDIS") == 0.02

    @pytest.mark.parametrize("given,expected", [
        (None, None), ("", None), ("junk", None), (0, None), (-3, None),
        (float("inf"), None), (float("nan"), None),
        (0.5, 0.5), ("2.5", 2.5), (10**9, 1000.0), (1e-9, 0.001),
    ])
    def test_a_factor_is_clamped_not_trusted(self, given, expected):
        assert clamp_scale(given) == expected

    def test_a_junk_factor_cannot_silently_shrink_someone(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": "huge"}})
        assert scale_of(scene, "Hinami") == 1.0

    def test_the_table_is_bounded(self):
        from spatial import _MAX_SCALES

        positions = {f"P{i}": "hall" for i in range(_MAX_SCALES + 20)}
        scales = {f"P{i}": 0.5 for i in range(_MAX_SCALES + 20)}
        scene = merge_scene_with_diff(_scene(positions=positions), {"scales": scales})
        assert len(scene["scales"]) == _MAX_SCALES


class TestSizeTiers:
    @pytest.mark.parametrize("factor,tier", [
        (0.01, "tiny"), (0.1, "tiny"), (0.15, "small"), (0.3, "small"),
        (1.0, "comparable"), (1.9, "comparable"),
        (2.0, "large"), (10, "large"), (25, "huge"), (500, "huge"),
    ])
    def test_tiers(self, factor, tier):
        assert size_tier(factor) == tier

    def test_tiny_means_it_fits_in_a_hand(self):
        """The label and the capability share a boundary deliberately."""
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.1}})
        assert size_tier(scale_of(scene, "Hinami")) == "tiny"
        assert size_relation(scene, "Hinami", "Tamamo")["fits_in_other_hand"]

    def test_ratio_between_two_bodies(self):
        scene = merge_scene_with_diff(
            _scene(), {"scales": {"Hinami": 0.1, "Tamamo": 2}})
        assert scale_ratio(scene, "Tamamo", "Hinami") == pytest.approx(20)
        assert scale_ratio(scene, "Hinami", "Tamamo") == pytest.approx(0.05)


class TestContactsCancelledByASizeChange:
    """The part that is enforced, not merely reported."""

    def _held_scene(self):
        return merge_scene_with_diff(_scene(), {"contact_ops": [_held()]})

    def test_shrinking_the_held_person_ends_the_grip(self):
        scene = self._held_scene()
        assert scene["contacts"]

        scene = merge_scene_with_diff(scene, {"scales": {"Hinami": 0.1}})

        # Not rescaled, not kept: cancelled. Whether anything equivalent is
        # still possible is the Director's call, next beat.
        assert scene["contacts"] == []

    def test_shrinking_the_holder_ends_it_too(self):
        scene = self._held_scene()
        scene = merge_scene_with_diff(scene, {"scales": {"Tamamo": 0.1}})
        assert scene["contacts"] == []

    def test_growing_ends_it(self):
        scene = self._held_scene()
        scene = merge_scene_with_diff(scene, {"scales": {"Tamamo": 6}})
        assert scene["contacts"] == []

    def test_returning_to_normal_also_ends_it(self):
        """Coming back from a shrink is just as much a reconfiguration."""
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.1}})
        scene = merge_scene_with_diff(scene, {"contact_ops": [_held()]})
        assert scene["contacts"]

        scene = merge_scene_with_diff(scene, {"scales": {"Hinami": 1}})
        assert scene["contacts"] == []

    def test_a_contact_between_untouched_bodies_survives(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Hinami": "hall", "Tamamo": "hall", "Bramwell": "hall"},
        ), {"contact_ops": [
            _held(),
            {"op": "add", "actor": "Bramwell", "target": "Tamamo",
             "manner": "lean"},
        ]})
        scene = merge_scene_with_diff(scene, {"scales": {"Hinami": 0.1}})

        # Only the holds involving the resized body end.
        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0]["actor"] == "Bramwell"

    def test_a_trivial_size_change_does_not_break_holds(self):
        """A growth spurt is not a reconfiguration."""
        scene = self._held_scene()
        scene = merge_scene_with_diff(scene, {"scales": {"Hinami": 1.1}})
        assert len(scene["contacts"]) == 1

    def test_the_director_can_re_establish_in_the_same_beat(self):
        """Cancellation and the new hold in one diff: the grip becomes what the
        new geometry allows."""
        scene = self._held_scene()
        scene = merge_scene_with_diff(scene, {
            "scales": {"Hinami": 0.05},
            "contact_ops": [{"op": "add", "actor": "Tamamo",
                             "actor_part": "hand", "target": "Hinami",
                             "target_part": "whole body", "manner": "carry"}],
        })

        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0]["manner"] == "carry"
        assert scene["contacts"][0]["target_part"] == "whole body"

    def test_it_reports_which_bodies_cancelled_contacts(self):
        scene = self._held_scene()
        scene["scales"] = {"Hinami": 0.1}
        broken = contacts_broken_by_scale_change(scene, {})

        assert broken == ["hinami"]
        assert scene["contacts"] == []

    def test_no_size_change_cancels_nothing(self):
        scene = self._held_scene()
        assert contacts_broken_by_scale_change(scene, dict(scene["scales"])) == []
        assert len(scene["contacts"]) == 1

    def test_nothing_is_stashed_in_the_saved_scene(self):
        """The scene blob is written verbatim; it must not collect scratch."""
        scene = self._held_scene()
        scene = merge_scene_with_diff(scene, {"scales": {"Hinami": 0.1}})
        assert not [k for k in scene if k.startswith("_")]


class TestFeasibilityIsReported:
    def test_a_much_larger_body_can_lift_a_much_smaller_one(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.1}})
        rel = size_relation(scene, "Tamamo", "Hinami")

        assert rel["can_lift_other"] is True
        assert rel["fits_in_other_hand"] is False   # that is the other way round
        assert rel["ratio"] == pytest.approx(10)

    def test_the_smaller_body_cannot_reach_or_lift(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.1}})
        rel = size_relation(scene, "Hinami", "Tamamo")

        assert rel["can_lift_other"] is False
        assert rel["can_be_lifted_by_other"] is True
        assert rel["fits_in_other_hand"] is True
        assert rel["can_reach_other_upper_body"] is False

    def test_comparable_bodies_permit_the_ordinary(self):
        scene = merge_scene_with_diff(_scene(), {})
        rel = size_relation(scene, "Hinami", "Tamamo")

        assert rel["ratio"] == 1.0
        assert rel["can_reach_other_upper_body"] is True
        assert rel["can_lift_other"] is False
        assert rel["can_be_lifted_by_other"] is False

    def test_precision_is_lost_before_reach_or_lifting(self):
        """Fine work needs a hand roughly proportionate to what it works on.
        This is the first capability a size gap takes away."""
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.2}})
        rel = size_relation(scene, "Tamamo", "Hinami")

        # Still able to reach and lift her; already unable to do fine work.
        assert rel["can_reach_other_upper_body"] is True
        assert rel["can_lift_other"] is True
        assert rel["can_do_fine_work_on_other"] is False

    def test_it_cuts_both_ways(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.2}})
        assert size_relation(scene, "Hinami", "Tamamo")[
            "can_do_fine_work_on_other"] is False

    def test_proportionate_bodies_keep_precision(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.5}})
        assert size_relation(scene, "Tamamo", "Hinami")[
            "can_do_fine_work_on_other"] is True

    def test_tiers_are_reported_for_both_sides(self):
        scene = merge_scene_with_diff(
            _scene(), {"scales": {"Hinami": 0.02, "Tamamo": 30}})
        rel = size_relation(scene, "Hinami", "Tamamo")

        assert rel["actor_tier"] == "tiny"
        assert rel["other_tier"] == "huge"


class TestGroundTruth:
    def test_a_normal_scene_produces_no_size_lines(self):
        scene = merge_scene_with_diff(_scene(), {})
        assert size_facts(scene, "Hinami", ["Tamamo"]) == []

    def test_the_observer_is_told_their_own_size(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.1}})
        facts = size_facts(scene, "Hinami", ["Tamamo"])
        assert any("tiny" in f for f in facts)

    def test_the_observer_is_told_who_towers_over_them(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.1}})
        facts = " ".join(size_facts(scene, "Hinami", ["Tamamo"]))
        assert "Tamamo" in facts and "hand around you" in facts

    def test_the_larger_body_is_told_the_other_could_be_picked_up(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.25}})
        facts = " ".join(size_facts(scene, "Tamamo", ["Hinami"]))
        assert "pick Hinami up" in facts

    def test_near_equal_sizes_say_nothing(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 1.2}})
        facts = size_facts(scene, "Tamamo", ["Hinami"])
        assert facts == []

    def test_size_reaches_the_narrator_before_the_contacts_it_invalidates(self):
        scene = merge_scene_with_diff(
            _scene(), {"scales": {"Hinami": 0.1},
                       "contact_ops": [{"op": "add", "actor": "Tamamo",
                                        "target": "Hinami", "manner": "hold"}]})
        facts = spatial_facts(scene, "Hinami", ["Tamamo"])

        joined = " ".join(facts)
        assert "tiny" in joined
        assert facts.index(next(f for f in facts if "tiny" in f)) < \
            facts.index(next(f for f in facts if "hold" in f))


class TestHygieneIsSafe:
    def test_a_malformed_scales_value_is_normalized(self):
        scene = _scene(scales="not a dict")
        assert normalize_scene_scales(scene)["scales"] == {}

    def test_an_empty_name_is_dropped(self):
        scene = _scene(scales={"": 0.5, "  ": 2})
        assert normalize_scene_scales(scene)["scales"] == {}

    def test_scale_of_tolerates_a_junk_scene(self):
        assert scale_of({}, "Hinami") == 1.0
        assert scale_of({"scales": "junk"}, "Hinami") == 1.0

    def test_lookup_is_case_insensitive(self):
        scene = merge_scene_with_diff(_scene(), {"scales": {"Hinami": 0.1}})
        assert scale_of(scene, "hinami") == 0.1


class TestSchema:
    def test_scales_survive_state_diff_validation(self):
        from schemas import StateDiff

        assert StateDiff(scales={"Hinami": 0.1}).dict()["scales"] == {"Hinami": 0.1}

    def test_the_director_shape_normalizer_accepts_it(self):
        from agents.director import _normalize_diff_shape

        assert _normalize_diff_shape({"scales": "junk"})["scales"] == {}
        assert _normalize_diff_shape({"scales": {"A": 2}})["scales"] == {"A": 2}
