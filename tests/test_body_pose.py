"""Body arrangement is objective state, not a visual-language default.

Room position says where a body is, station says where within that room, and
contact says what touches. None of those imply standing. The pose ledger owns
posture, support, relative arrangement, and physical constraint across beats.
"""

from __future__ import annotations

from agents.director import (_evidence_present, _normalize_diff_shape,
                             _opening_pose_snapshots)
from agents.perception import (_novel_visible_appearances,
                               _observer_scene_payload,
                               _strip_unknown_pose_claims)
from prompts import DEFAULT_PROMPTS
from schemas import DirectorEstablish, StateDiff, validate_llm_output_strict
from spatial import merge_scene_with_diff, pose_facts


def _scene():
    return {
        "rooms": {"studio": {
            "name": "Studio", "adjacent": [],
            "anchors": {"work_table": {"desc": "a padded work table"}},
        }},
        "positions": {"Mara": "studio", "Ivo": "studio", "Witness": "studio"},
        "stations": {
            "Mara": {"at": "work_table", "near": ["Ivo"]},
            "Ivo": {"at": "work_table", "near": ["Mara"]},
        },
        "entities": {},
        "contacts": [],
        "poses": {
            "Ivo": {
                "posture": "lying supine", "support": "work_table",
                "relative_to": "Mara", "relation": "beneath",
                "constraint": "pinned", "detail": "shoulders held down",
            },
            "Mara": {
                "posture": "leaning over", "support": "work_table",
                "relative_to": "Ivo", "relation": "above",
                "constraint": "", "detail": "",
            },
        },
    }


class TestSchemaAndOpening:
    def test_pose_round_trips_through_both_director_schemas(self):
        poses = _scene()["poses"]
        assert StateDiff(poses=poses).dict()["poses"] == poses
        assert DirectorEstablish(poses=poses).dict()["poses"] == poses
        report = validate_llm_output_strict("director_resolve", {
            "resolved_event": "Ivo remains pinned beneath Mara.",
            "state_diff": {"poses": poses},
        })
        assert report.valid, report.errors
        assert report.output["state_diff"]["poses"] == poses

    def test_legacy_opening_posture_seeds_durable_pose(self):
        out = {
            "entity_states": {"Ivo": {"posture": "kneeling"}},
            "poses": {"Mara": {"posture": "seated"}},
        }
        assert _opening_pose_snapshots(out) == {
            "Ivo": {"posture": "kneeling"},
            "Mara": {"posture": "seated"},
        }

    def test_explicit_pose_wins_over_legacy_posture(self):
        out = {
            "entity_states": {"Ivo": {"posture": "standing"}},
            "poses": {"Ivo": {"posture": "lying", "support": "cot"}},
        }
        assert _opening_pose_snapshots(out)["Ivo"] == {
            "posture": "lying", "support": "cot",
        }

    def test_normalization_and_reconciliation_recognize_pose(self):
        assert _normalize_diff_shape({"poses": "bad"})["poses"] == {}
        assert _evidence_present(
            {"poses": {"Ivo": {"posture": "lying"}}},
            {"category": "pose", "subject": "Ivo", "change": "Ivo lies down."})


class TestPosePersistence:
    def test_pose_persists_across_an_unrelated_beat(self):
        merged = merge_scene_with_diff(_scene(), {})
        assert merged["poses"]["Ivo"]["posture"] == "lying supine"
        assert merged["poses"]["Ivo"]["relation"] == "beneath"
        assert merged["poses"]["Ivo"]["constraint"] == "pinned"

    def test_touched_pose_is_a_complete_replacement(self):
        merged = merge_scene_with_diff(_scene(), {
            "poses": {"Ivo": {"posture": "standing"}},
        })
        assert merged["poses"]["Ivo"] == {
            "posture": "standing", "support": "", "relative_to": "",
            "relation": "", "constraint": "", "detail": "",
        }

    def test_null_or_empty_pose_clears_the_snapshot(self):
        assert "Ivo" not in merge_scene_with_diff(
            _scene(), {"poses": {"Ivo": None}})["poses"]
        assert "Ivo" not in merge_scene_with_diff(
            _scene(), {"poses": {"Ivo": {}}})["poses"]

    def test_room_separation_clears_relative_relation_not_own_posture(self):
        scene = _scene()
        scene["rooms"]["hall"] = {"name": "Hall", "adjacent": []}
        merged = merge_scene_with_diff(scene, {"positions": {"Mara": "hall"}})
        ivo = merged["poses"]["Ivo"]
        assert ivo["posture"] == "lying supine"
        assert ivo["support"] == "work_table"
        assert ivo["relative_to"] == ""
        assert ivo["relation"] == ""
        assert ivo["constraint"] == ""

    def test_authoritative_spatial_facts_carry_the_arrangement(self):
        facts = pose_facts(_scene(), "Mara", ["Ivo"])
        joined = " ".join(facts)
        assert "Ivo's current body pose" in joined
        assert "posture: lying supine" in joined
        assert "relative to you (beneath)" in joined
        assert "constraint: pinned" in joined

    def test_pose_is_the_posture_authority_for_entityless_player_bodies(self):
        from comfort import rest_affording

        scene = _scene()
        scene["rooms"]["studio"]["anchors"]["work_table"][
            "desc"] = "a cushioned work table"
        assert rest_affording(scene, "Ivo")


class TestObserverProjection:
    def test_visible_pose_reaches_perception_without_becoming_standing(self):
        payload = _observer_scene_payload(
            _scene(), {"name": "Mara", "room": "studio", "visible_rooms": []},
            {"Mara": "you", "Ivo": "Ivo", "Witness": "Witness"})
        assert payload["poses"]["Ivo"] == _scene()["poses"]["Ivo"] | {
            "relative_to": "you",
        }
        assert "standing" not in str(payload["poses"]["Ivo"]).casefold()
        assert payload["pose_unknown"] == ["Witness"]

    def test_legacy_missing_pose_is_explicit_uncertainty_not_a_default(self):
        scene = _scene()
        scene["poses"] = {}
        payload = _observer_scene_payload(
            scene,
            {"name": "Mara", "room": "lab", "visible_rooms": []},
            {"Mara": "you", "Ivo": "Ivo"},
        )
        assert payload["poses"] == {}
        assert payload["pose_unknown"] == ["you", "Ivo"]

    def test_unsupported_static_pose_is_removed_but_other_detail_survives(self):
        view, dropped = _strip_unknown_pose_claims(
            "Ivo, a traveler in a red coat, stands before you. "
            "His sleeve is wet. Mara's voice stands out clearly.",
            ["Ivo", "Mara"],
        )
        assert "stands before" not in view
        assert "His sleeve is wet." in view
        assert "Mara's voice stands out clearly." in view
        assert dropped == [
            "Ivo, a traveler in a red coat, stands before you."]

    def test_unseen_relative_identity_is_not_leaked(self):
        scene = _scene()
        scene["positions"]["Mara"] = "elsewhere"
        payload = _observer_scene_payload(
            scene, {"name": "Ivo", "room": "studio", "visible_rooms": []},
            {"Ivo": "you"})
        own = payload["poses"]["you"]
        assert "relative_to" not in own
        assert "relation" not in own
        assert own["constraint"] == "pinned"

    def test_familiar_stable_appearance_is_not_reintroduced(self):
        result = _novel_visible_appearances(
            _scene(), {"Ivo": "Ivo, a beautiful six-tailed person."},
            {"Ivo": True}, observer_name="Mara", recognized=["Ivo"])
        assert result == {}

    def test_unknown_or_visibly_changed_appearance_is_included(self):
        appearances = {"Ivo": "Ivo, a beautiful six-tailed person."}
        visual = {"Ivo": True}
        assert "Ivo" in _novel_visible_appearances(
            _scene(), appearances, visual,
            observer_name="Mara", recognized=[])
        assert "Ivo" in _novel_visible_appearances(
            _scene(), appearances, visual,
            observer_name="Mara", recognized=["Ivo"], changed=["Ivo"])

    def test_prompts_forbid_default_standing_and_appearance_roll_calls(self):
        perception = DEFAULT_PROMPTS["perception"]
        resolve = DEFAULT_PROMPTS["director_resolve"]
        assert "Presence and visibility do not imply standing" in perception
        assert "scene.pose_unknown" in perception
        assert "fresh roll-call of age, beauty, species traits" in perception
        assert "BODY POSE AND RELATIVE ARRANGEMENT" in resolve
        assert "Never default an unspecified pose to standing" in resolve
