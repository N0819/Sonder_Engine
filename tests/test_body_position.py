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
        "positions": {"Bramwell": "bedroom", "Hinami": "bedroom"},
        "entities": {}, "contacts": [],
    }
    scene.update(over)
    return scene


def _hold(actor="Bramwell", actor_part="hand", target="Hinami",
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
        assert scene["contacts"][0]["actor"] == "Bramwell"
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
            positions={"Bramwell": "bedroom", "Hinami": "bedroom",
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
            {"op": "remove", "actor": "Bramwell", "target": "Hinami"}]})

        # Parts omitted ends all contact between the two: ending a hold must
        # not require recalling exactly which parts were recorded.
        assert scene["contacts"] == []

    def test_removal_works_in_either_direction(self):
        """Contact is physically symmetric; a release named the other way round
        is the same release."""
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        scene = merge_scene_with_diff(scene, {"contact_ops": [
            {"op": "remove", "actor": "Hinami", "target": "Bramwell"}]})
        assert scene["contacts"] == []

    def test_removing_one_part_leaves_the_others(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", **_hold(actor_part="hand", target_part="wrist")},
            {"op": "add", **_hold(actor_part="mouth", target_part="throat")},
        ]})
        scene = merge_scene_with_diff(scene, {"contact_ops": [
            {"op": "remove", "actor": "Bramwell", "target": "Hinami",
             "actor_part": "hand"}]})

        assert [c["actor_part"] for c in scene["contacts"]] == ["mouth"]

    def test_clear_releases_everything_one_person_is_part_of(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Bramwell": "bedroom", "Hinami": "bedroom",
                       "Tamamo": "bedroom"},
        ), {"contact_ops": [
            {"op": "add", **_hold()},
            {"op": "add", **_hold(actor="Tamamo", target="Hinami")},
            {"op": "add", **_hold(actor="Tamamo", target="Bramwell")},
        ]})
        scene = merge_scene_with_diff(
            scene, {"contact_ops": [{"op": "clear", "actor": "Hinami"}]})

        # Everything Hinami was part of, on either side, and nothing else.
        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0]["actor"] == "Tamamo"
        assert scene["contacts"][0]["target"] == "Bramwell"

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
            positions={"Bramwell": "bedroom", "Hinami": "hall"},
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
            positions={"Bramwell": "bedroom", "Hinami": "bedroom",
                       "Tamamo": "bedroom"},
        ), {"contact_ops": [
            {"op": "add", **_hold()},
            {"op": "add", **_hold(actor="Tamamo", target_part="shoulder")},
            {"op": "add", **_hold(actor="Tamamo", target="Bramwell")},
        ]})

        # The reader that did not exist: this was only answerable by re-reading
        # a prose paragraph and hoping.
        on_hinami = contacts_of(scene, "Hinami")
        assert len(on_hinami) == 2
        assert {c["actor"] for c in on_hinami} == {"Bramwell", "Tamamo"}

    def test_it_finds_a_person_on_either_side(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        assert len(contacts_of(scene, "Bramwell")) == 1
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
        assert contact_phrase(_hold()) == "Bramwell's hand grips Hinami's waist"
        assert contact_phrase(_hold(actor_part="", target_part="", manner="hold")) \
            == "Bramwell holds Hinami"


class TestNarratorGroundTruth:
    """Contact is the fact a narrator most easily contradicts -- describing
    hands that let go a beat ago, or a hold that was never recorded."""

    def test_the_observers_own_contact_is_stated(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        facts = spatial_facts(scene, "Hinami", ["Bramwell"])

        assert any("waist" in f and "hand" in f for f in facts)

    def test_contact_between_two_others_in_view_is_stated(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Bramwell": "bedroom", "Hinami": "bedroom",
                       "Tamamo": "bedroom"},
        ), {"contact_ops": [
            {"op": "add", **_hold(actor="Tamamo", target="Bramwell")}]})

        facts = spatial_facts(scene, "Hinami", ["Tamamo", "Bramwell"])
        assert any("Tamamo" in f and "Bramwell" in f for f in facts)

    def test_contact_among_people_out_of_view_is_not_stated(self):
        scene = merge_scene_with_diff(_scene(
            positions={"Bramwell": "bedroom", "Hinami": "bedroom",
                       "Tamamo": "bedroom"},
        ), {"contact_ops": [
            {"op": "add", **_hold(actor="Tamamo", target="Bramwell")}]})

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

        # Bramwell is present and holding her, but not a source the observer can
        # name: no line, rather than a line naming a stranger.
        facts = spatial_facts(scene, "Hinami", [])
        assert not any("Bramwell" in f for f in facts)

    def test_a_released_hold_stops_being_stated(self):
        scene = merge_scene_with_diff(
            _scene(), {"contact_ops": [{"op": "add", **_hold()}]})
        scene = merge_scene_with_diff(scene, {"contact_ops": [
            {"op": "remove", "actor": "Bramwell", "target": "Hinami"}]})

        assert not any("waist" in f
                       for f in spatial_facts(scene, "Hinami", ["Bramwell"]))


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


class TestMirroredAssertions:
    """One physical contact stated from both sides is still one contact. Both
    bodies describing the same hold is exactly how the old per-entity shape
    produced two records that drifted."""

    def test_the_same_hold_from_both_sides_is_one_record(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", "actor": "Bramwell", "actor_part": "hand",
             "target": "Hinami", "target_part": "wrist", "manner": "grip"},
            {"op": "add", "actor": "Hinami", "actor_part": "wrist",
             "target": "Bramwell", "target_part": "hand", "manner": "grip"},
        ]})
        assert len(scene["contacts"]) == 1

    def test_the_mirror_updates_the_record_rather_than_twinning_it(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", "actor": "Bramwell", "actor_part": "hand",
             "target": "Hinami", "target_part": "wrist", "manner": "rest"}]})
        scene = merge_scene_with_diff(scene, {"contact_ops": [
            {"op": "add", "actor": "Hinami", "actor_part": "wrist",
             "target": "Bramwell", "target_part": "hand", "manner": "grip"}]})

        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0]["manner"] == "grip"

    def test_different_parts_are_different_contacts_not_mirrors(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", "actor": "Bramwell", "actor_part": "hand",
             "target": "Hinami", "target_part": "wrist", "manner": "grip"},
            {"op": "add", "actor": "Hinami", "actor_part": "hand",
             "target": "Bramwell", "target_part": "wrist", "manner": "grip"},
        ]})
        # Each holding the other's wrist is two holds, not one stated twice.
        assert len(scene["contacts"]) == 2


class TestLiftingContactOutOfEntityState:
    """Contact the Director wrote into an entity's own state -- the shape that
    predates contact_ops, and the one a model still reaches for. It is lifted
    into contacts and REMOVED from the state, so one contact has one record.

    Every fixture here is a verbatim shape taken from live chats.
    """

    def _lift(self, entities, positions=None):
        scene = _scene(
            positions=positions or {"Hinami": "bedroom", "Tamamo": "bedroom"},
            entities=entities,
        )
        return merge_scene_with_diff(scene, {})

    def test_the_documented_old_shape_converts(self):
        """`target` plus a proximity that means contact."""
        scene = self._lift({"Bramwell": {
            "name": "Bramwell",
            "state": {"proximity": "pressed_fully_against", "target": "Hinami",
                      "posture": "grinding_with_full_contact"}}},
            positions={"Hinami": "bedroom", "Bramwell": "bedroom"})

        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0]["actor"] == "Bramwell"
        assert scene["contacts"][0]["manner"] == "press"
        state = scene["entities"]["Bramwell"]["state"]
        assert "target" not in state
        assert "proximity" not in state

        # Once movement prunes the lifted relation, sharing a room again must
        # not recreate it from stale copies of the legacy assertion.
        scene = merge_scene_with_diff(
            scene, {"positions": {"Bramwell": "hall"}})
        assert scene["contacts"] == []
        scene = merge_scene_with_diff(
            scene, {"positions": {"Bramwell": "bedroom"}})
        assert scene["contacts"] == []

    def test_mere_nearness_does_not_become_contact(self):
        """`close_on_bed` is proximity, not contact -- stations model that.
        Inventing a hold is worse than missing one: contact becomes ground
        truth the narrator is told."""
        scene = self._lift({"Bramwell": {
            "name": "Bramwell",
            "state": {"proximity": "close_on_bed", "target": "Hinami",
                      "posture": "leaning_in"}}},
            positions={"Hinami": "bedroom", "Bramwell": "bedroom"})

        assert scene["contacts"] == []

    def test_an_invented_key_naming_a_person_converts(self):
        scene = self._lift({"hinami": {
            "name": "Hinami", "state": {"leaning_against": "tamamo"}}})

        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0] == {
            "actor": "Hinami", "actor_part": "", "target": "Tamamo",
            "target_part": "", "manner": "lean", "unasserted": 0}

    def test_the_key_name_yields_the_body_part(self):
        scene = self._lift({"hinami": {
            "name": "Hinami", "state": {"tails_wrapped_around": "Tamamo"}}})

        contact = scene["contacts"][0]
        assert contact["actor_part"] == "tails"
        assert contact["manner"] == "wrap"

    def test_the_value_can_carry_the_targets_part(self):
        """`squished_against: "tamamo_side"` is Tamamo's side."""
        scene = self._lift({"hinami": {
            "name": "Hinami", "state": {"squished_against": "tamamo_side"}}})

        contact = scene["contacts"][0]
        assert contact["target"] == "Tamamo"
        assert contact["target_part"] == "side"
        assert contact["manner"] == "press"

    def test_adjacency_words_are_left_completely_alone(self):
        """`alongside`/`beside` are not contact. Not converted, not stripped."""
        scene = self._lift({"hinami": {
            "name": "Hinami", "state": {"alongside": "Tamamo",
                                        "beside": "Tamamo"}}})

        assert scene["contacts"] == []
        assert scene["entities"]["hinami"]["state"]["alongside"] == "Tamamo"

    def test_a_converted_key_is_removed_from_the_state(self):
        scene = self._lift({"hinami": {
            "name": "Hinami", "state": {"posture": "curled_up",
                                        "leaning_against": "tamamo"}}})

        state = scene["entities"]["hinami"]["state"]
        assert "leaning_against" not in state       # one truth, not two
        assert state["posture"] == "curled_up"      # not contact; untouched

    def test_a_value_naming_nobody_is_left_alone(self):
        scene = self._lift({"hinami": {
            "name": "Hinami",
            "state": {"contact": "bodies_aligned_in_warmth"}}})

        assert scene["contacts"] == []
        assert "contact" in scene["entities"]["hinami"]["state"]

    @pytest.mark.parametrize("key", [
        "transit", "link", "phase", "hatch", "posture", "activity",
        "held_items", "zone", "destination_room", "route_room",
    ])
    def test_structurally_load_bearing_keys_are_never_touched(self, key):
        """Movement, portals and perception's own backstop read these."""
        scene = self._lift({"hinami": {
            "name": "Hinami", "state": {key: "Tamamo"}}})

        assert key in scene["entities"]["hinami"]["state"]

    def test_lifted_contact_then_obeys_the_same_hygiene(self):
        scene = self._lift({"hinami": {
            "name": "Hinami", "state": {"leaning_against": "tamamo"}}})
        assert scene["contacts"]

        # Walking away ends it, exactly like a contact recorded by an op.
        scene = merge_scene_with_diff(scene, {"positions": {"Hinami": "hall"}})
        assert scene["contacts"] == []

    def test_a_contact_across_two_rooms_is_never_lifted(self):
        scene = self._lift(
            {"hinami": {"name": "Hinami", "state": {"leaning_against": "tamamo"}}},
            positions={"Hinami": "bedroom", "Tamamo": "hall"})
        assert scene["contacts"] == []

    def test_both_bodies_describing_the_hold_yields_one_contact(self):
        scene = self._lift({
            "hinami": {"name": "Hinami", "state": {"held_by": "Tamamo"}},
            "Tamamo": {"name": "Tamamo", "state": {"holding": "Hinami"}},
        })
        assert len(scene["contacts"]) == 1

    def test_the_live_chat_40_state_lifts_cleanly(self):
        """Verbatim from the live scene that prompted this."""
        scene = self._lift({
            "hinami": {"name": "Hinami", "kind": "traveller", "state": {
                "posture": "curled_up_in_nest_eyes_closed",
                "leaning_against": "tamamo",
                "contact": "bodies_aligned_in_warmth",
                "squished_against": "tamamo_side",
                "alongside": "Tamamo",
                "tails_wrapped_around": "Tamamo"}},
            "Tamamo": {"name": "Tamamo", "kind": "traveller", "state": {
                "posture": "reclining_in_nest_embracing_hinami",
                "beside": "Hinami"}},
        })

        manners = {c["manner"] for c in scene["contacts"]}
        assert manners == {"lean", "press", "wrap"}
        # The narrator can now be told, in order, what is actually touching.
        assert all(c["target"] == "Tamamo" for c in scene["contacts"])

    def test_an_entity_with_no_position_is_skipped(self):
        scene = self._lift({"ghost": {
            "name": "Ghost", "state": {"leaning_against": "tamamo"}}})
        assert scene["contacts"] == []

    def test_a_state_that_is_not_a_dict_is_tolerated(self):
        scene = self._lift({"hinami": {"name": "Hinami", "state": "prose"}})
        assert scene["contacts"] == []

    def test_prose_is_not_parsed_for_contact(self):
        """A description paragraph is left as the descriptive text it is.
        Regex over prose would manufacture holds nobody asserted."""
        scene = self._lift({"hinami": {
            "name": "Hinami",
            "state": {"description": "her hand resting on Tamamo's shoulder"}}})

        assert scene["contacts"] == []
        assert "description" in scene["entities"]["hinami"]["state"]


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


class TestAgeingRetiresContactNobodyReasserts:
    """Position pruning ends a hold when someone walks away. Nothing ended one
    that simply stopped being true while both bodies stayed put -- so in a
    scene set in one room, contact was append-only, and a touch from four
    beats ago was still asserted as current. Perception reads the scene as
    present truth and narrates it as happening now.

    The Director already re-asserts a hold that persists and stops mentioning
    one that ended; ageing is what reads that signal.
    """

    def test_a_contact_nobody_reasserts_retires(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", **_hold(actor_part="lips", target_part="forehead",
                                  manner="kiss")}]})
        assert len(scene["contacts"]) == 1

        # Two later beats that talk about contact without mentioning the kiss.
        for _ in range(2):
            scene = merge_scene_with_diff(scene, {"contact_ops": [
                {"op": "add", **_hold(actor_part="palm",
                                      target_part="sternum", manner="press")}]})

        assert [c["actor_part"] for c in scene["contacts"]] == ["palm"]

    def test_a_reasserted_contact_never_ages(self):
        """The sustained hold is the one the Director keeps naming."""
        scene = _scene()
        for _ in range(6):
            scene = merge_scene_with_diff(scene, {"contact_ops": [
                {"op": "add", **_hold(actor_part="palm",
                                      target_part="sternum", manner="press")}]})

        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0]["unasserted"] == 0

    def test_reassertion_from_the_other_side_also_resets_the_clock(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", **_hold(actor_part="palm", target_part="sternum",
                                  manner="press")}]})
        for _ in range(4):
            # The mirror: the same hold stated from the other body.
            scene = merge_scene_with_diff(scene, {"contact_ops": [
                {"op": "add", "actor": "Hinami", "actor_part": "sternum",
                 "target": "Bramwell", "target_part": "palm",
                 "manner": "press"}]})

        assert len(scene["contacts"]) == 1

    def test_a_beat_with_no_contact_ops_ages_nothing(self):
        """The failure a naive implementation introduces.

        Silence about contact is only evidence on a beat that speaks about
        contact at all. Live, the Director routinely emits nothing for a beat;
        ageing on those would retire a whole arrangement over a couple of
        quiet exchanges.
        """
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", **_hold(actor_part="palm", target_part="sternum",
                                  manner="press")}]})

        for _ in range(8):
            scene = merge_scene_with_diff(scene, {})          # no contact_ops
        for _ in range(8):
            scene = merge_scene_with_diff(scene, {"contact_ops": []})

        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0]["unasserted"] == 0

    def test_junk_ops_are_not_evidence(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", **_hold()}]})
        for _ in range(6):
            scene = merge_scene_with_diff(
                scene, {"contact_ops": [{"op": "add"}, {"op": "nonsense"}]})

        assert len(scene["contacts"]) == 1

    def test_simultaneity_is_not_capped(self):
        """Ageing removes what is no longer true; it must not remove what is.

        Every one of these is asserted on the same beat, so all of them stand
        -- including two contacts sharing one actor part, which a body moving
        between two places within a beat genuinely produces.
        """
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", **_hold(actor_part="palm", target_part="sternum",
                                  manner="press")},
            {"op": "add", **_hold(actor_part="tongue", target_part="belly",
                                  manner="lick")},
            {"op": "add", **_hold(actor_part="tongue", target_part="throat",
                                  manner="lick")},
            {"op": "add", **_hold(actor_part="thigh", target_part="hip",
                                  manner="rest")},
        ]})

        assert len(scene["contacts"]) == 4

    def test_a_scene_saved_before_ageing_existed_reads_as_fresh(self):
        """Back-compat: no `unasserted` key means 0, not "infinitely stale"."""
        scene = _scene(contacts=[_hold()])
        scene = merge_scene_with_diff(scene, {"contact_ops": [
            {"op": "add", **_hold(actor_part="palm", target_part="sternum",
                                  manner="press")}]})

        assert len(scene["contacts"]) == 2


class TestAnActIsNotAState:
    """`manner` carried two different kinds of word with one storage rule.

    `rest`, `press` and `hold` describe a state: they can hold still and stay
    true. `kiss`, `pinch` and `flick` name the ACT that produced a touch, and
    an act is over as soon as the story moves on. Storing both identically
    meant a kiss became a permanent fact, and every consumer that reads the
    scene as present truth narrated it as happening now.
    """

    def test_a_momentary_manner_renders_as_the_touch_it_left(self):
        assert contact_phrase(_hold(actor_part="lips", target_part="forehead",
                                    manner="kiss")) == (
            "Bramwell's lips are against Hinami's forehead")

    def test_a_durable_manner_keeps_its_own_verb(self):
        assert contact_phrase(_hold(manner="rest")) == (
            "Bramwell's hand rests against Hinami's waist")
        assert contact_phrase(_hold(manner="press")) == (
            "Bramwell's hand presses against Hinami's waist")

    def test_an_unknown_manner_is_still_inflected_only_once(self):
        """The fiction is wider than any list, and 'throttleses' is not a word."""
        assert contact_phrase(_hold(manner="throttles")) == (
            "Bramwell's hand throttles Hinami's waist")

    def test_an_act_retires_a_beat_before_a_hold_does(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", **_hold(actor_part="lips", target_part="forehead",
                                  manner="kiss")},
            {"op": "add", **_hold(actor_part="palm", target_part="sternum",
                                  manner="press")},
        ]})
        assert len(scene["contacts"]) == 2

        # One later beat that speaks about contact without naming either.
        scene = merge_scene_with_diff(scene, {"contact_ops": [
            {"op": "add", **_hold(actor_part="tail", target_part="ankle",
                                  manner="coil")}]})

        standing = {c["actor_part"] for c in scene["contacts"]}
        assert "lips" not in standing, "the act is over"
        assert "palm" in standing, "the hold is not"

    def test_a_reasserted_act_still_stands(self):
        """A kiss the Director keeps naming is a kiss still happening."""
        scene = _scene()
        for _ in range(5):
            scene = merge_scene_with_diff(scene, {"contact_ops": [
                {"op": "add", **_hold(actor_part="lips",
                                      target_part="forehead", manner="kiss")}]})

        assert len(scene["contacts"]) == 1

    def test_narrator_ground_truth_states_contact_as_state(self):
        scene = merge_scene_with_diff(_scene(), {"contact_ops": [
            {"op": "add", **_hold(actor_part="lips", target_part="forehead",
                                  manner="kiss")}]})
        facts = spatial_facts(scene, "Hinami", ["Bramwell"])

        contact_lines = [f for f in facts if "forehead" in f]
        assert contact_lines
        assert not any("kiss" in f for f in contact_lines), (
            "ground truth must not hand the narrator an act to re-stage")

    def test_classification_is_total_on_junk(self):
        from spatial import contact_is_momentary

        assert contact_is_momentary(_hold(manner="kiss")) is True
        assert contact_is_momentary(_hold(manner="rest")) is False
        assert contact_is_momentary({}) is False
        assert contact_is_momentary(None) is False


class TestStandingContactIsWrittenForItsReader:
    """The clause goes into a perceiver's own payload, where that perceiver is
    "you". Handing them a third-person sentence naming themselves canonically
    is the objective-state-into-a-subjective-context pattern the engine
    forbids elsewhere, and it invites the person drift it sounds like. Body
    parts are also routinely plural, which one verb form cannot serve."""

    def test_the_observers_own_side_is_second_person(self):
        assert contact_phrase(_hold(actor_part="palm", target_part="sternum",
                                    manner="press"), you="Hinami") == (
            "Bramwell's palm presses against your sternum")
        assert contact_phrase(_hold(actor_part="palm", target_part="sternum",
                                    manner="press"), you="Bramwell") == (
            "your palm presses against Hinami's sternum")

    def test_a_bare_name_becomes_you_and_takes_the_plural_verb(self):
        assert contact_phrase(_hold(actor_part="", target_part="",
                                    manner="hold"), you="Bramwell") == (
            "you hold Hinami")

    def test_no_observer_keeps_the_third_person(self):
        assert contact_phrase(_hold(manner="rest")) == (
            "Bramwell's hand rests against Hinami's waist")

    def test_a_plural_body_part_takes_a_plural_verb(self):
        assert contact_phrase(_hold(actor_part="fingers", manner="touch")) == (
            "Bramwell's fingers are against Hinami's waist")
        assert contact_phrase(_hold(actor_part="thighs", manner="rest")) == (
            "Bramwell's thighs rest against Hinami's waist")

    def test_a_singular_part_ending_in_s_is_not_mistaken_for_plural(self):
        assert contact_phrase(_hold(actor_part="solar plexus",
                                    manner="press")) == (
            "Bramwell's solar plexus presses against Hinami's waist")

    def test_an_unknown_manner_is_not_double_inflected_for_either_number(self):
        assert contact_phrase(_hold(actor_part="hand", manner="throttles")) == (
            "Bramwell's hand throttles Hinami's waist")
        assert contact_phrase(_hold(actor_part="hands", manner="throttle")) == (
            "Bramwell's hands throttle Hinami's waist")

    def test_an_unknown_observer_name_changes_nothing(self):
        plain = contact_phrase(_hold())
        assert contact_phrase(_hold(), you="Somebody Else") == plain
        assert contact_phrase(_hold(), you="") == plain
        assert contact_phrase(_hold(), you=None) == plain
