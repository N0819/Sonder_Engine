"""Body position tracking: who is in contact with whom, and where.

Contact used to live as prose inside an entity's own `state` -- a single
whole-body `target`, a `proximity` word, and a `description` paragraph, written
by the model and read back by the model with nothing structural in between.
Four costs, all visible in live play:

* it could not say WHERE. One whole-body target, so a hand on a shoulder and a
  grip on a wrist were the same fact, and holding two people at once was
  unsayable.
* it was stored per entity, so one contact became two records -- one on each
  body -- free to drift apart.
* nothing ever cleared it. The paragraph persisted verbatim until the model
  happened to rewrite it, so a grip survived the person walking away, and a
  tail "coiled around the leg" for three beats became "around the waist" with
  no transition and no record of either.
* no reader could query it, so the narrator had only prose to re-read and was
  free to contradict it.

A contact is a RELATION, so it is stored once, at scene level, in the grain
`stations` already established: a list that deterministic hygiene prunes at
every merge. Movement ending a hold falls out of that hygiene rather than
depending on the Director remembering.
"""

from __future__ import annotations

import pytest

from spatial import (
    apply_contact_ops,
    contact_phrase,
    contacts_of,
    merge_scene_with_diff,
    normalize_scene_contacts,
    spatial_facts,
)


def _scene(**over):
    scene = {
        "rooms": {"bedroom": {"name": "Bedroom", "adjacent": []},
                  "hall": {"name": "Hall", "adjacent": []}},
        "positions": {"Lilaeve Voss": "bedroom", "Hinami": "bedroom"},
        "entities": {}, "contacts": [],
    }
    scene.update(over)
    return scene


def _hold(actor="Lilaeve Voss", actor_part="hand", target="Hinami",
          target_part="waist", manner="grip"):
    return {"actor": actor, "actor_part": actor_part, "target": target,
            "target_part": target_part, "manner": manner}


class TestRecordingContact:
    def test_a_contact_is_recorded_once_not_on_both_bodies(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})

        # One relation, one record. The old shape wrote a paragraph onto each
        # body and let the two drift.
        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0]["actor"] == "Lilaeve Voss"
        assert scene["contacts"][0]["target_part"] == "waist"

    def test_body_parts_are_kept(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        contact = scene["contacts"][0]

        assert contact["actor_part"] == "hand"
        assert contact["target_part"] == "waist"
        assert contact["manner"] == "grip"

    def test_one_person_can_hold_several_things_at_once(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Lilaeve Voss": "bedroom", "Hinami": "bedroom",
                       "Tamamo": "bedroom"},
        ), {"contact_ops": [
            {"op": "add", **_hold(actor_part="hand", target_part="wrist")},
            {"op": "add", **_hold(actor_part="mouth", target_part="throat",
                                  manner="kiss")},
            {"op": "add", **_hold(target="Tamamo", actor_part="tail",
                                  target_part="ankle", manner="coil")},
        ]})

        # Unsayable in the old shape: one whole-body `target` per entity.
        assert len(scene["contacts"]) == 3
        assert {c["target"] for c in scene["contacts"]} == {"Hinami", "Tamamo"}

    def test_re_asserting_a_contact_updates_it_rather_than_stacking(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold(manner="rest")}]})
        scene = merge_scene_with_diff(
            scene, {"contact_ops": [{"op": "add", **_hold(manner="grip")}]})

        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0]["manner"] == "grip"

    def test_a_manner_outside_the_vocabulary_is_kept(self):
        """The fiction is wider than any list."""
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold(manner="Throttles")}]})
        assert scene["contacts"][0]["manner"] == "throttles"

    def test_a_body_is_not_in_contact_with_itself(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", "actor": "Hinami", "target": "Hinami",
             "manner": "touch"}]})
        assert scene["contacts"] == []

    def test_a_contact_naming_nobody_is_dropped(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", "actor": "Hinami", "target": "", "manner": "grip"},
            {"op": "add", "actor": "", "target": "Hinami"},
            {"op": "add"},
            "not a dict",
        ]})
        assert scene["contacts"] == []


class TestEndingContact:
    def test_removing_by_the_pair_ends_it(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        scene = merge_scene_with_diff(scene, {"contact_ops": [
            {"op": "remove", "actor": "Lilaeve Voss", "target": "Hinami"}]})

        # Parts omitted ends all contact between the two: ending a hold must
        # not require recalling exactly which parts were recorded.
        assert scene["contacts"] == []

    def test_removal_works_in_either_direction(self):
        """Contact is physically symmetric; a release named the other way round
        is the same release."""
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        scene = merge_scene_with_diff(scene, {"contact_ops": [
            {"op": "remove", "actor": "Hinami", "target": "Lilaeve Voss"}]})
        assert scene["contacts"] == []

    def test_removing_one_part_leaves_the_others(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", **_hold(actor_part="hand", target_part="wrist")},
            {"op": "add", **_hold(actor_part="mouth", target_part="throat")},
        ]})
        scene = merge_scene_with_diff(scene, {"contact_ops": [
            {"op": "remove", "actor": "Lilaeve Voss", "target": "Hinami",
             "actor_part": "hand"}]})

        assert [c["actor_part"] for c in scene["contacts"]] == ["mouth"]

    def test_clear_releases_everything_one_person_is_part_of(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Lilaeve Voss": "bedroom", "Hinami": "bedroom",
                       "Tamamo": "bedroom"},
        ), {"contact_ops": [
            {"op": "add", **_hold()},
            {"op": "add", **_hold(actor="Tamamo", target="Hinami")},
            {"op": "add", **_hold(actor="Tamamo", target="Lilaeve Voss")},
        ]})
        scene = merge_scene_with_diff(
            scene, {"contact_ops": [{"op": "clear", "actor": "Hinami"}]})

        # Everything Hinami was part of, on either side, and nothing else.
        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0]["actor"] == "Tamamo"
        assert scene["contacts"][0]["target"] == "Lilaeve Voss"

    def test_a_bare_clear_releases_the_scene(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        scene = merge_scene_with_diff(scene, {"contact_ops": [{"op": "clear"}]})
        assert scene["contacts"] == []


class TestMovementClearsContactByItself:
    """The bug that made contact go stale: nothing ended it. Positions now do,
    the same way a room change already self-heals a station anchor."""

    def test_walking_out_of_the_room_ends_the_hold(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        assert scene["contacts"]

        scene = merge_scene_with_diff(scene, {"positions": {"Hinami": "hall"}})

        # No contact_op required, and none was sent.
        assert scene["contacts"] == []

    def test_leaving_the_scene_entirely_ends_it(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        scene["positions"].pop("Hinami")
        assert normalize_scene_contacts(scene)["contacts"] == []

    def test_staying_in_the_room_keeps_it(self):
        """The other half: a hold must not evaporate on an unrelated beat."""
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        scene = merge_scene_with_diff(scene, {"positions": {"Hinami": "bedroom"}})
        scene = merge_scene_with_diff(scene, {})

        assert len(scene["contacts"]) == 1

    def test_an_op_cannot_smuggle_in_an_impossible_contact(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Lilaeve Voss": "bedroom", "Hinami": "hall"},
        ), {"contact_ops": [{"op": "add", **_hold()}]})

        # Hygiene runs after the ops, so a hold across two rooms never lands.
        assert scene["contacts"] == []

    def test_coming_back_does_not_resurrect_a_dropped_hold(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        scene = merge_scene_with_diff(scene, {"positions": {"Hinami": "hall"}})
        scene = merge_scene_with_diff(scene, {"positions": {"Hinami": "bedroom"}})

        assert scene["contacts"] == []


class TestReading:
    def test_what_is_touching_this_person(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Lilaeve Voss": "bedroom", "Hinami": "bedroom",
                       "Tamamo": "bedroom"},
        ), {"contact_ops": [
            {"op": "add", **_hold()},
            {"op": "add", **_hold(actor="Tamamo", target_part="shoulder")},
            {"op": "add", **_hold(actor="Tamamo", target="Lilaeve Voss")},
        ]})

        # The reader that did not exist: this was only answerable by re-reading
        # a prose paragraph and hoping.
        on_hinami = contacts_of(scene, "Hinami")
        assert len(on_hinami) == 2
        assert {c["actor"] for c in on_hinami} == {"Lilaeve Voss", "Tamamo"}

    def test_it_finds_a_person_on_either_side(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        assert len(contacts_of(scene, "Lilaeve Voss")) == 1
        assert len(contacts_of(scene, "Hinami")) == 1

    def test_lookup_is_case_insensitive(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        assert contacts_of(scene, "hinami")

    def test_an_uninvolved_person_has_no_contacts(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        assert contacts_of(scene, "Tamamo") == []
        assert contacts_of(scene, "") == []

    def test_a_contact_reads_as_a_plain_clause(self):
        assert contact_phrase(_hold()) == "Lilaeve Voss's hand grips Hinami's waist"
        assert contact_phrase(_hold(actor_part="", target_part="", manner="hold")) \
            == "Lilaeve Voss holds Hinami"


class TestNarratorGroundTruth:
    """Contact is the fact a narrator most easily contradicts -- describing
    hands that let go a beat ago, or a hold that was never recorded."""

    def test_the_observers_own_contact_is_stated(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        facts = spatial_facts(scene, "Hinami", ["Lilaeve Voss"])

        assert any("waist" in f and "hand" in f for f in facts)

    def test_contact_between_two_others_in_view_is_stated(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Lilaeve Voss": "bedroom", "Hinami": "bedroom",
                       "Tamamo": "bedroom"},
        ), {"contact_ops": [
            {"op": "add", **_hold(actor="Tamamo", target="Lilaeve Voss")}]})

        facts = spatial_facts(scene, "Hinami", ["Tamamo", "Lilaeve Voss"])
        assert any("Tamamo" in f and "Lilaeve Voss" in f for f in facts)

    def test_contact_among_people_out_of_view_is_not_stated(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Lilaeve Voss": "bedroom", "Hinami": "bedroom",
                       "Tamamo": "bedroom"},
        ), {"contact_ops": [
            {"op": "add", **_hold(actor="Tamamo", target="Lilaeve Voss")}]})

        # Not in the observer's source_names: not theirs to know.
        facts = spatial_facts(scene, "Hinami", [])
        assert not any("Tamamo" in f for f in facts)

    def test_a_hold_by_someone_unnameable_yields_no_named_line(self):
        """These clauses carry canonical names. A contact involving someone the
        observer cannot name would hand the narrator a name the observer has no
        way to know -- the leak this engine exists to prevent. Both parties must
        be nameable, exactly like the proximity clauses."""
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})

        # Lilaeve is present and holding her, but not a source the observer can
        # name: no line, rather than a line naming a stranger.
        facts = spatial_facts(scene, "Hinami", [])
        assert not any("Lilaeve" in f for f in facts)

    def test_a_released_hold_stops_being_stated(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        scene = merge_scene_with_diff(scene, {"contact_ops": [
            {"op": "remove", "actor": "Lilaeve Voss", "target": "Hinami"}]})

        assert not any("waist" in f
                       for f in spatial_facts(scene, "Hinami", ["Lilaeve Voss"]))


class TestHygieneIsSafe:
    def test_a_scene_with_no_contacts_is_untouched(self):
        scene = merge_scene_with_diff({"positions": {}, "rooms": {},
                                       "entities": {}}, {})
        assert scene.get("contacts") in (None, [])

    def test_a_malformed_contacts_value_is_normalized(self):
        scene = _scene(contacts="not a list")
        assert normalize_scene_contacts(scene)["contacts"] == []

    def test_the_list_is_capped(self):
        from spatial import _MAX_CONTACTS

        positions = {"Hinami": "bedroom"}
        ops = []
        for i in range(_MAX_CONTACTS + 25):
            positions[f"P{i}"] = "bedroom"
            ops.append({"op": "add", "actor": f"P{i}", "target": "Hinami",
                        "target_part": f"spot{i}", "manner": "touch"})

        scene = merge_scene_with_diff(
            _scene(positions=positions), {"contact_ops": ops})
        assert len(scene["contacts"]) == _MAX_CONTACTS

    def test_ops_are_tolerant_of_junk(self):
        scene = _scene()
        apply_contact_ops(scene, "not a list")
        apply_contact_ops(scene, [None, 7, "x", {"op": "nonsense"}])
        assert isinstance(scene["contacts"], list)


class TestSchema:
    def test_contact_ops_survive_state_diff_validation(self):
        from schemas import StateDiff

        diff = StateDiff(contact_ops=[{"op": "add", **_hold()}])
        assert diff.dict()["contact_ops"][0]["target_part"] == "waist"

    def test_the_director_shape_normalizer_accepts_it(self):
        from agents.director import _normalize_diff_shape

        assert _normalize_diff_shape({"contact_ops": "junk"})["contact_ops"] == []
        kept = _normalize_diff_shape({"contact_ops": [{"op": "add"}]})
        assert kept["contact_ops"] == [{"op": "add"}]
