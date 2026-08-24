"""`uncovered` is durable history, and a ledger that lost it can be repaired.

Until `88aee71`, `attire.advance` rebuilt every region without carrying
`uncovered` forward, so the flag that licenses a region to show its authored
`beneath` prose lived exactly one beat: the next wardrobe change anywhere on
that body wiped it. Measured in chat 86, one checkpoint per turn -- arms lit at
t10 and were dark by t12, torso t12 -> t13, waist t13 -> t14, groin and legs
t14 -> t15. Feet survived only because nothing proposed that region again, so a
body bare in seven places rendered its authored surface in one of them.

The engine fix is forward-only: the licence is earned by a garment LEAVING a
region, and a body already stripped has none left to lose. These cover the
repair that reads the loss back out of a chat's own recorded history.

The distinction under test is the one no single scene carries: a region that
was stripped in play looks exactly like a region that was never dressed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from scene_lint import (  # noqa: E402
    heal_exposure,
    muted_surfaces,
    observe_exposure,
    strip_state_word_garments,
)
from story import attire  # noqa: E402


BENEATH = "Soft, tanned skin across the chest and stomach."


def _scene(garments, *, uncovered=False, beneath=BENEATH, region="torso"):
    entry = {"garments": list(garments), "beneath": beneath}
    if uncovered:
        entry["uncovered"] = True
    return {"attire": {"Hinami": {"regions": {region: entry}}}}


def _tank(state="worn"):
    return {"name": "fitted tank top", "state": state}


def _history(*scenes):
    """Replay scenes in turn order and return what the history proves."""
    known, worn_before = {}, {}
    for scene in scenes:
        observe_exposure(scene, known, worn_before)
    return known


class TestWhatTheHistoryProves:
    def test_a_garment_leaving_a_region_is_the_evidence(self):
        known = _history(_scene([_tank()]), _scene([]))
        assert known == {"Hinami": {"torso"}}

    def test_the_one_beat_flag_is_evidence_even_after_it_was_wiped(self):
        """The shape actually stored: lit for one checkpoint, then dark."""
        known = _history(_scene([_tank()]),
                         _scene([], uncovered=True),
                         _scene([]))
        assert known == {"Hinami": {"torso"}}

    def test_a_region_never_dressed_proves_nothing(self):
        """Tamamo's head and hands, Mirelle's hands and feet: bare from the
        opening, authored `beneath`, and correctly silent."""
        known = _history(_scene([]), _scene([]), _scene([]))
        assert known == {}

    def test_an_ornament_is_not_a_covering(self):
        """A hair clip leaving a head never uncovered it, so its departure is
        not evidence the head was bared."""
        clip = {"name": "feather hair clip", "state": "worn", "attaches": True}
        known = _history(_scene([clip], region="head"),
                         _scene([], region="head"))
        assert known == {}

    def test_an_older_engines_spelling_counts(self):
        """A garment still seated under `state: "removed"` is the same fact
        `uncovered` records, and `perceptible_region_surfaces` reads both."""
        known = _history(_scene([_tank("removed")]))
        assert known == {"Hinami": {"torso"}}


class TestWhatTheRepairWrites:
    def test_it_restores_the_licence_and_the_prose_comes_back(self):
        live = _scene([])
        assert muted_surfaces(live) == [("Hinami", "torso")]

        assert heal_exposure(live, {"Hinami": {"torso"}})

        region = live["attire"]["Hinami"]["regions"]["torso"]
        assert region["uncovered"] is True
        assert muted_surfaces(live) == []
        surface = attire.perceptible_region_surfaces(
            live["attire"]["Hinami"]["regions"], beneath_visible=True)
        assert surface["torso"].startswith("bare — ")
        assert BENEATH in surface["torso"]

    def test_it_never_invents_the_flag_under_clothing(self):
        """Something covering the region again is the one state this must not
        write into: the live path gets its own chance when that covering
        leaves, and asserting it here would claim a baring nothing recorded."""
        live = _scene([_tank()])
        assert not heal_exposure(live, {"Hinami": {"torso"}})
        assert "uncovered" not in live["attire"]["Hinami"]["regions"]["torso"]

    def test_it_is_idempotent(self):
        live = _scene([])
        assert heal_exposure(live, {"Hinami": {"torso"}})
        assert not heal_exposure(live, {"Hinami": {"torso"}})

    def test_a_region_with_no_authored_prose_is_not_a_muted_surface(self):
        """The flag is still restored -- it is a fact about the body, not
        about whether there is prose to show -- but nothing was silenced."""
        live = _scene([], beneath="")
        assert muted_surfaces(live) == []
        assert heal_exposure(live, {"Hinami": {"torso"}})
        assert live["attire"]["Hinami"]["regions"]["torso"]["uncovered"] is True


class TestCausalOrder:
    def test_a_checkpoint_is_never_healed_before_the_beat_that_earned_it(self):
        """Restoring the flag onto every checkpoint at once would assert a
        body was bared on turns when it was still dressed."""
        dressed, stripped = _scene([_tank()]), _scene([])
        known, worn_before = {}, {}

        observe_exposure(dressed, known, worn_before)
        assert not heal_exposure(dressed, {b: set(r) for b, r in known.items()})
        assert "uncovered" not in dressed["attire"]["Hinami"]["regions"]["torso"]

        observe_exposure(stripped, known, worn_before)
        assert heal_exposure(stripped, {b: set(r) for b, r in known.items()})
        assert stripped["attire"]["Hinami"]["regions"]["torso"]["uncovered"]


class TestTheCauseIsFixed:
    def test_advance_now_carries_uncovered_forward(self):
        """The regression itself: without this the repair is a treadmill, and
        the next wardrobe change re-mutes every region it just restored."""
        previous = {"torso": {"garments": [], "beneath": BENEATH,
                              "uncovered": True}}
        proposed = {"torso": {"garments": [], "beneath": BENEATH}}
        assert attire.advance(previous, proposed)["torso"]["uncovered"] is True


class TestStateWordsWornAsGarments:
    """Seven bodies in four stories are dressed in a word.

    A name no garment table recognises falls to the region fallback, which is
    why every measured one landed on the TORSO: chats 52/60/61 wear `removed`
    and `worn` there, chat 85 wears `bare feet`. The live path refuses these
    now (`attire.is_bare_garment_state`); it cannot unwear the stored ones.
    """

    def _dressed_in(self, word):
        return {"attire": {"Hinami": {
            "wearing": ["feather hair clip", word],
            "regions": {"torso": {
                "garments": [{"name": word, "state": "worn",
                              "attaches": False}],
                "beneath": BENEATH}}}}}

    def test_a_state_word_is_unwore_from_region_and_wearing(self):
        for word in ("removed", "worn", "bare feet"):
            sc = self._dressed_in(word)
            assert strip_state_word_garments(sc), word
            entry = sc["attire"]["Hinami"]
            assert entry["wearing"] == ["feather hair clip"], word
            assert entry["regions"]["torso"]["garments"] == [], word

    def test_a_real_garment_is_never_unwore(self):
        sc = self._dressed_in("fitted tank top")
        assert not strip_state_word_garments(sc)
        assert sc["attire"]["Hinami"]["wearing"] == [
            "feather hair clip", "fitted tank top"]

    def test_unwearing_a_phantom_does_not_license_the_region(self):
        """It never covered anything, so its departure bares nothing. Only a
        chat's recorded history may earn the flag."""
        sc = self._dressed_in("bare feet")
        strip_state_word_garments(sc)
        assert "uncovered" not in sc["attire"]["Hinami"]["regions"]["torso"]
        assert muted_surfaces(sc) == [("Hinami", "torso")]

    def test_it_unblocks_a_region_the_history_had_already_earned(self):
        """Chat 85 exactly: the torso's real garments left turns ago, but the
        phantom sitting there read as a covering, so the flag could not be
        written under it."""
        sc = self._dressed_in("bare feet")
        assert not heal_exposure(sc, {"Hinami": {"torso"}})
        strip_state_word_garments(sc)
        assert heal_exposure(sc, {"Hinami": {"torso"}})
        assert muted_surfaces(sc) == []

    def test_it_is_idempotent(self):
        sc = self._dressed_in("removed")
        assert strip_state_word_garments(sc)
        assert not strip_state_word_garments(sc)
