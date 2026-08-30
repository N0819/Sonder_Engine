"""The engine's own register must not reach the page.

Three separate places were printing the engine's bookkeeping into English
that a mind then read as prose:

  * a part-qualified pose referent -- `<owner>.<part>` -- composed verbatim,
    dot and all ('Hinami is lying on Mirelle Sulmirath.tongue on you'), while
    its id-spelled twin `mirelle_sulmirath.hands` hit the id-shaped drop and
    was lost whole, taking owner AND part with it;
  * one ledger field holding two spellings of one body, because
    `normalize_scene_subjects` folded `poses.relative_to` and never
    `poses.support`;
  * a magnitude BAND written into the free-text `amount` field and joined as
    though it were a noun ('Your palm registers moderate of oil being
    deposited on it').

None of this is about any story. The rule is that the view is COMPOSED, not
quoted: every line in it is typed data rendered into English so a mind can
read it, and a token, a spelling or a band showing through is the engine
being legible where the fiction should be.
"""

from __future__ import annotations

import json
import re

import pytest

from agents.composer import pose_percepts, render_view
from language_runtime import raw_card


def _scene(poses, **kw):
    scene = {
        "rooms": {"h": {"name": "Hall", "light": "bright"}},
        "positions": {"Observer": "h", "Actor": "h"},
        "entities": {"observer_id": {"name": "Observer", "kind": "body"}},
        "poses": poses,
    }
    scene.update(kw)
    return scene


def _render(scene, observer="Observer", others=(("Actor", "Actor"),)):
    percepts = pose_percepts(
        scene, observer, [{"name": n} for n, _ in others],
        {n: label for n, label in others})
    return render_view(percepts).text, percepts


class TestAPartIsARereferentLikeAnyOther:
    def test_a_part_qualified_support_renders_as_language_not_a_token(self):
        text, _ = _render(_scene({"Actor": {
            "posture": "leaning", "support": "Observer.shoulder"}}))
        assert text == "Actor is leaning on your shoulder."
        assert re.search(r"\w\.\w", text) is None

    def test_one_body_at_two_granularities_takes_one_preposition(self):
        """The body in `relative_to` and a place ON it in `support` are one
        referent at two granularities. Comparing whole strings let both
        render, which is where the second preposition came from."""
        text, _ = _render(_scene({"Actor": {
            "posture": "leaning", "support": "Observer.shoulder",
            "relative_to": "Observer", "relation": "against"}}))
        assert text == "Actor is leaning against your shoulder."
        assert text.count("shoulder") == 1
        assert " on " not in text

    def test_the_part_resolves_by_owner_whichever_spelling_names_it(self):
        by_name, _ = _render(_scene({"Actor": {
            "posture": "leaning", "support": "Observer.shoulder"}}))
        by_id, _ = _render(_scene({"Actor": {
            "posture": "leaning", "support": "observer_id.shoulder"}}))
        assert by_name == by_id
        assert "observer_id" not in by_id

    def test_a_part_of_a_body_you_were_not_shown_is_dropped_with_its_owner(
            self):
        """The firewall answer is INHERITED from the owner, never re-decided
        for the part: a body absent from the display map is one this observer
        was not shown, and its shoulder discloses it just as well."""
        scene = _scene({"Actor": {"posture": "leaning",
                                  "support": "Absent.shoulder"},
                        "Absent": {"posture": "standing"}})
        scene["positions"]["Absent"] = "elsewhere"
        text, percepts = _render(scene)
        assert text == "Actor is leaning."
        assert "Absent" not in text
        assert "someone" not in text
        assert not percepts[0].data.get("support")

    def test_an_owners_part_reads_as_that_owners(self):
        """A third body the observer HAS been shown keeps its own label."""
        scene = _scene({"Actor": {
            "posture": "leaning", "support": "Third.shoulder"}})
        scene["positions"]["Third"] = "h"
        text, _ = _render(scene, others=(("Actor", "Actor"), ("Third", "Kai")))
        assert text == "Actor is leaning on Kai's shoulder."

    def test_a_dot_the_scene_does_not_know_is_left_as_written(self):
        """An unresolvable owner half means the value was never a part
        token -- free text keeps its own punctuation."""
        text, _ = _render(_scene({"Actor": {
            "posture": "sitting", "support": "St. Ives"}}))
        assert text == "Actor is sitting on St. Ives."

    def test_a_name_carrying_a_period_is_never_split(self):
        """A spelling the scene knows AS A WHOLE is not a compound."""
        scene = _scene({"Actor": {"posture": "leaning",
                                  "support": "Dr. Vance"}})
        scene["positions"]["Dr. Vance"] = "h"
        text, _ = _render(scene,
                          others=(("Actor", "Actor"), ("Dr. Vance", "Vance")))
        assert text == "Actor is leaning on Vance."


class TestOnePoseFieldHoldsOneSpelling:
    def _scene(self, support, relative_to):
        return {
            "rooms": {"h": {"name": "Hall"}},
            "entities": {"kestrel_vane": {"name": "Kestrel", "kind": "body"}},
            "positions": {"Kestrel": "h", "Other": "h"},
            "poses": {"Other": {"posture": "kneeling", "support": support,
                                "relative_to": relative_to}},
        }

    def test_a_part_qualified_support_folds_by_its_owner(self):
        from world.spatial import normalize_scene_subjects

        scene = self._scene("kestrel_vane.hand", "kestrel_vane")
        folded = normalize_scene_subjects(scene)
        pose = scene["poses"]["Other"]
        assert pose["support"] == "Kestrel.hand"
        assert pose["relative_to"] == "Kestrel"
        assert any(where == "poses.support" for where, _old, _new in folded)

    def test_the_canonical_spelling_is_a_fixed_point(self):
        from world.spatial import normalize_scene_subjects

        scene = self._scene("Kestrel.hand", "Kestrel")
        normalize_scene_subjects(scene)
        assert scene["poses"]["Other"]["support"] == "Kestrel.hand"

    def test_an_anchor_id_support_is_never_renamed_by_the_fold(self):
        """The reason this is a part-owner fold rather than a whole-value
        one: `poses.support` also legitimately names a room ANCHOR keyed by
        id, and the anchor lookup is by that id."""
        from world.spatial import (normalize_scene_poses,
                                   normalize_scene_subjects)

        scene = {
            "rooms": {"h": {"name": "Hall",
                            "anchors": {"bench_low": {"name": "Low Bench"}}}},
            "entities": {"bench_low": {"name": "Low Bench",
                                       "kind": "furniture"}},
            "positions": {"Low Bench": "h", "Actor": "h"},
            "poses": {"Actor": {"posture": "sitting", "support": "bench_low"}},
        }
        normalize_scene_subjects(scene)
        assert scene["poses"]["Actor"]["support"] == "bench_low"
        normalize_scene_poses(scene)
        assert scene["poses"]["Actor"]["support"] == "bench_low"


class TestAMagnitudeIsNotANoun:
    def test_a_band_reaches_the_view_as_a_quantity(self):
        from world.spatial import _material_phrase

        assert _material_phrase("moderate", "oil") == "a moderate amount of oil"
        assert "moderate of" not in _material_phrase("moderate", "oil")

    def test_every_band_has_a_phrase(self):
        from world.spatial import SUBSTANCE_AMOUNT_BANDS, _material_phrase

        for band in SUBSTANCE_AMOUNT_BANDS:
            phrase = _material_phrase(band, "oil")
            assert phrase.endswith(" oil")
            assert not phrase.startswith(band + " of")

    def test_the_fictions_own_wording_passes_through(self):
        """`substance_amount_band` matches the whole string only, so a
        phrase that merely contains a band word is the author's, not the
        engine's."""
        from world.spatial import _material_phrase

        assert _material_phrase("a thin smear", "oil") == "a thin smear of oil"

    def test_an_empty_amount_leaves_no_stray_preposition(self):
        from world.spatial import _material_phrase

        assert _material_phrase("", "oil") == "oil"
        assert _material_phrase(None, "oil") == "oil"

    def test_the_event_clause_uses_it(self):
        from world.spatial import substance_event_clause

        scene = {"rooms": {"h": {"name": "Hall"}},
                 "positions": {"You": "h", "Other": "h"}}
        clause = substance_event_clause(
            {"op": "add", "substance": "oil", "amount": "moderate",
             "placement": "surface", "target_part": "palm",
             "target": "You", "source": "Other"}, you="You", scene=scene)
        assert "a moderate amount of oil" in clause
        assert "moderate of" not in clause


class TestTheRuleReachedTheNarrator:
    @pytest.mark.parametrize("lang", ["en", "ja"])
    def test_both_cards_say_the_view_is_composed(self, lang):
        narrator = raw_card(lang)["prompts"]["narrator"]
        marker = ("IT IS COMPOSED, NOT QUOTED" if lang == "en"
                  else "引用ではなく合成されたもの")
        assert marker in narrator

    def test_the_duration_flag_is_a_craft_tell(self):
        """The deterministic floor under the prompt clause. The string is a
        literal the engine builds to mark a sensation as ongoing rather than
        an event; it is not a phrase prose writes."""
        from agents.narration import _craft_tells

        tells = _craft_tells(
            "The warmth stays, continuous while the contact holds.")
        assert tells

    def test_it_does_not_fire_on_ordinary_prose(self):
        from agents.narration import _craft_tells

        assert not any(
            "continuous while" in str(t)
            for t in _craft_tells("She held on while the ship turned."))
