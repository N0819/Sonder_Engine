"""Body arrangement is objective state, not a visual-language default.

Room position says where a body is, station says where within that room, and
contact says what touches. None of those imply standing. The pose ledger owns
posture, support, relative arrangement, and physical constraint across beats.
"""

from __future__ import annotations

from agents.director import (_evidence_present, _normalize_diff_shape,
                             _opening_pose_snapshots)
from agents import composer
from llm.prompts import DEFAULT_PROMPTS
from llm.schemas import DirectorEstablish, StateDiff, validate_llm_output_strict
from world.spatial import merge_scene_with_diff, pose_facts


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
        from world.comfort import rest_affording

        scene = _scene()
        scene["rooms"]["studio"]["anchors"]["work_table"][
            "desc"] = "a cushioned work table"
        assert rest_affording(scene, "Ivo")


class TestObserverProjection:
    """The pose reaches a mind as a typed percept, not as a scene payload for
    a model to read. `perception._observer_scene_payload` built that payload
    and `_strip_unknown_pose_claims` swept a model's invented postures back out
    of finished prose; neither has a caller since the composer became the
    writer, and the second has no successor because the failure it swept up
    -- prose asserting a posture the ledger never recorded -- cannot be
    produced by a renderer that only realises percepts."""

    CO_PRESENT = [{"name": "Ivo"}, {"name": "Mara"}, {"name": "Witness"}]

    def _poses(self, scene, observer, display_map):
        return composer.pose_percepts(
            scene, observer, self.CO_PRESENT, display_map)

    def test_visible_pose_reaches_perception_without_becoming_standing(self):
        percepts = self._poses(
            _scene(), "Mara",
            {"Mara": "you", "Ivo": "Ivo", "Witness": "Witness"})
        ivo = [p for p in percepts if p.source_label == "Ivo"]

        assert ivo
        assert ivo[0].data["posture"] == "lying supine"
        assert ivo[0].data["constraint"] == "pinned"
        assert ivo[0].data["relative_to"] == "you"
        view = composer.render_view(percepts, mode="character").text
        assert "standing" not in view.casefold()

    def test_a_missing_pose_makes_no_claim_at_all(self):
        """The absence IS the uncertainty. The scene payload spelled it as an
        explicit `pose_unknown` roll-call because a model was reading it and
        silence would have been filled in; nothing reads a percept list but the
        renderer, and a posture nobody recorded produces no sentence."""
        scene = _scene()
        scene["poses"] = {}
        percepts = self._poses(scene, "Mara", {"Mara": "you", "Ivo": "Ivo"})

        assert percepts == []
        assert composer.render_view(percepts, mode="character").text == ""

    def test_a_body_with_no_within_room_tier_yields_no_pose(self):
        """Posture is rendered AGAINST the furniture and bodies around it, and
        those referents belong to a room the observer is not in."""
        scene = _scene()
        scene["positions"]["Ivo"] = "elsewhere"
        percepts = self._poses(
            scene, "Mara", {"Mara": "you", "Ivo": "Ivo"})

        assert [p.source_label for p in percepts] == ["you"]

    def test_unseen_relative_identity_is_not_leaked(self):
        """Ivo's own pose still names its relation -- he can feel he is pinned
        beneath someone -- but the someone is the label his display map earned,
        never the canonical name of a body he cannot see."""
        scene = _scene()
        scene["positions"]["Mara"] = "elsewhere"
        percepts = self._poses(scene, "Ivo", {"Ivo": "you"})
        own = [p for p in percepts if p.source_label == "you"][0]

        assert own.channel == "interoception"
        assert own.data["constraint"] == "pinned"
        assert own.data["relative_to"] == "someone"
        assert "Mara" not in composer.render_view(
            percepts, mode="character").text

    def test_familiar_stable_appearance_is_not_reintroduced(self):
        """First mention only, in every mode. `_novel_visible_appearances`
        answered the same question one layer up and by name; `prev_described`
        answers it by source key, so a re-described body cannot slip through on
        a spelling."""
        ivo = composer.appearance_percept(
            "Ivo", "Ivo", "Ivo, a beautiful six-tailed person.")
        first = composer.render_view([ivo], mode="character")

        assert "six-tailed" in first.text
        assert composer.render_view(
            [ivo], mode="character", prev_described=first.described).text == ""

    def test_a_visibly_changed_appearance_is_included_again(self):
        ivo = composer.appearance_percept(
            "Ivo", "Ivo", "Ivo, a beautiful six-tailed person.", force=True)
        described = composer.render_view([ivo], mode="character").described

        assert "six-tailed" in composer.render_view(
            [ivo], mode="character", prev_described=described).text

    def test_prompts_forbid_default_standing_and_appearance_roll_calls(self):
        # The perception half of this test asserted a prompt no model reads --
        # perception composes deterministically and its prompt is gone from
        # the packs. The spatial specialist is a live model call, so its half
        # is the half that can still regress.
        resolve = DEFAULT_PROMPTS["director_spatial"]
        assert "BODY POSE AND RELATIVE ARRANGEMENT" in resolve
        assert "Never default an unspecified pose to standing" in resolve
