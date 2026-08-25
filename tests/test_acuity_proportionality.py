"""Acuity is proportionality, and the ledger that measures it had no reader.

`scales` has been in the scene blob, `size_relation` has computed what a
magnitude gap permits, and `size_facts` has written it out in words -- and
none of it reached a mind. `size_facts`' only caller is `spatial_facts`,
which nothing on the live path imports: the composer reimplemented presence
and pose as typed percepts and never picked up size. So an observer received
a body's authored texture verbatim across a 4x gap, and was never told the
body was four times its size in the first place.

Two halves, on two thresholds that are deliberately different:

  * DETAIL stops resolving at 4x. A body far off the observer's own scale
    delivers form and mass, never texture -- the larger observer is above the
    detail, the smaller one is inside it. The band is `size_relation`'s own
    precision boundary rather than a fresh constant, because the hand and the
    eye must not drift apart.
  * A size STATEMENT starts at 2x, and rides the standing presence sentence,
    because relative magnitude qualifies every other clause in the view.

Between 2x and 4x the view says how big the other is and still delivers
texture: knowing someone is twice your size is not the same question as
whether you can read their skin.

Both halves no-op byte-identically on a scene that writes no `scales` entry,
which is nearly every scene.
"""

from __future__ import annotations

import json

import pytest

from agents.common import observer_body_regions
from agents.composer import presence_percepts, render_view
from world.spatial import detail_resolves_between


def _scene(scales=None):
    scene = {
        "rooms": {"h": {"name": "Hall", "light": "bright"}},
        "positions": {"Observer": "h", "Giant": "h"},
        "attire": {"Giant": {"regions": {"legs": {"garments": [
            {"name": "sheer stockings", "kind": "stockings",
             "state": "worn", "coverage": "legs",
             "description": "barely visible copper-gold hair beneath"}]}}}},
    }
    if scales is not None:
        scene["scales"] = scales
    return scene


class TestDetailStopsResolving:
    def test_a_proportionate_body_delivers_its_texture(self):
        rows = observer_body_regions(
            _scene(), "Observer", {"Giant": "the tall woman"})
        surfaces = rows[0]["regions"]
        assert "copper-gold hair" in surfaces["legs"]

    def test_a_body_far_off_your_scale_delivers_form_not_texture(self):
        rows = observer_body_regions(
            _scene({"Observer": 1.0, "Giant": 5.0}), "Observer",
            {"Giant": "the tall woman"})
        surfaces = rows[0]["regions"]
        assert "copper-gold hair" not in surfaces["legs"]

    def test_the_region_still_arrives_and_still_says_covered_or_bare(self):
        """It SUBTRACTS. A coarsened region is not a removed one -- the
        observer still sees whether the leg is covered, and by what."""
        scene = _scene({"Observer": 1.0, "Giant": 5.0})
        scene["attire"]["Giant"]["regions"]["legs"] = {
            "garments": [{"name": "wool trousers", "kind": "trousers",
                          "state": "worn", "coverage": "legs",
                          "description": "napped, worn shiny at the knee"}]}
        rows = observer_body_regions(scene, "Observer",
                                     {"Giant": "the tall woman"})
        surface = rows[0]["regions"]["legs"]
        assert "wool trousers" in surface
        assert "napped" not in surface

    def test_it_is_symmetric(self):
        """The larger observer is above the detail; the smaller one is inside
        it. Neither is reading a REGION as a surface."""
        assert not detail_resolves_between(
            _scene({"Observer": 1.0, "Giant": 5.0}), "Observer", "Giant")
        assert not detail_resolves_between(
            _scene({"Observer": 5.0, "Giant": 1.0}), "Observer", "Giant")

    def test_a_body_is_always_proportionate_to_itself(self):
        """The self row can never be coarsened, by construction: a ratio to
        yourself is 1.0, so no `same_subject` check is needed to protect it."""
        scene = _scene({"Observer": 1.0, "Giant": 5.0})
        scene["attire"]["Observer"] = {"regions": {"legs": {"garments": [
            {"name": "canvas trousers", "kind": "trousers", "state": "worn",
             "coverage": "legs", "description": "an old burn scar showing"}]}}}
        rows = observer_body_regions(scene, "Observer", {"Observer": "you"})
        assert "an old burn scar" in rows[0]["regions"]["legs"]

    def test_an_unscaled_scene_is_unchanged(self):
        with_ledger = observer_body_regions(
            _scene({"Observer": 1.0, "Giant": 1.0}), "Observer",
            {"Giant": "the tall woman"})
        without = observer_body_regions(
            _scene(), "Observer", {"Giant": "the tall woman"})
        assert with_ledger == without


class TestTheViewSaysHowBig:
    def _presence(self, scene, others=(("Giant", "the tall woman"),)):
        return presence_percepts(
            scene, "Observer", [{"name": n} for n, _ in others],
            {n: label for n, label in others})

    def test_an_ordinary_pair_says_nothing_about_size(self):
        percepts = self._presence(_scene())
        assert "size" not in percepts[0].data
        assert "far larger" not in render_view(percepts).text

    def test_a_body_far_larger_is_said_to_be(self):
        percepts = self._presence(_scene({"Observer": 1.0, "Giant": 3.0}))
        assert percepts[0].data["size"] == "much_larger"
        assert "far larger than you" in render_view(percepts).text

    def test_a_body_far_smaller_is_said_to_be(self):
        percepts = self._presence(_scene({"Observer": 3.0, "Giant": 1.0}))
        assert percepts[0].data["size"] == "much_smaller"
        assert "far smaller than you" in render_view(percepts).text

    def test_the_hand_held_readings_win_over_the_liftable_ones(self):
        """Extreme-first, because a body that fits in a hand also satisfies
        the liftable predicate."""
        assert self._presence(
            _scene({"Observer": 1.0, "Giant": 0.05}))[0].data["size"] \
            == "palm_sized"
        assert self._presence(
            _scene({"Observer": 0.05, "Giant": 1.0}))[0].data["size"] \
            == "hand_holds_you"

    def test_between_the_thresholds_size_is_stated_and_detail_survives(self):
        """The two thresholds are deliberately different and must not be
        tidied into agreement."""
        scene = _scene({"Observer": 1.0, "Giant": 3.0})
        assert self._presence(scene)[0].data["size"] == "much_larger"
        rows = observer_body_regions(scene, "Observer",
                                     {"Giant": "the tall woman"})
        assert "copper-gold hair" in rows[0]["regions"]["legs"]

    def test_a_body_that_changes_size_re_earns_its_presence_line(self):
        small = self._presence(_scene())[0].dedupe_key
        large = self._presence(
            _scene({"Observer": 1.0, "Giant": 3.0}))[0].dedupe_key
        assert small != large

    def test_no_canonical_name_rides_the_percept(self):
        """The label is a closed engine token, so `body_key`'s IR invariant
        still holds."""
        percept = self._presence(_scene({"Observer": 1.0, "Giant": 3.0}))[0]
        assert "Giant" not in json.dumps(percept.data)


class TestTheVocabularyIsLanguageData:
    @pytest.mark.parametrize("lang", ["en", "ja"])
    def test_both_packs_carry_every_label(self, lang):
        """`_SIZE_PHRASES` is read at import time, so a missing key is not a
        wording problem -- it is a KeyError in every test in the repo."""
        card = json.load(open(f"language_packs/{lang}/cards/compositor.json",
                              encoding="utf-8"))
        assert set(card["size_phrases"]) == {
            "palm_sized", "hand_holds_you", "much_smaller", "much_larger"}

    def test_the_labels_the_composer_mints_are_exactly_those(self):
        from agents.composer import _SIZE_PHRASES, _size_label

        minted = set()
        for ratio in (0.02, 0.3, 1.0, 3.0, 50.0):
            label = _size_label(
                {"scales": {"Observer": 1.0, "Other": ratio}},
                "Observer", "Other")
            if label:
                minted.add(label)
        assert minted <= set(_SIZE_PHRASES)
        assert minted == set(_SIZE_PHRASES)
