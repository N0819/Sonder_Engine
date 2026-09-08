"""What a character withholds shapes how much they say (review D23).

`suggested_lines` was a seeded coin toss over the author's band: the same
number for a laconic bodyguard and a barfly, the same number whether a
question was hanging in the air or not, and no relation at all to the desire
the character is sitting on. `voice.verbosity` -- a field the card editor
offers and the schema defaults -- was read by NOTHING.

Three facts the engine already holds decide the number now, and the author's
band still bounds all three. The band and its `variance` dial are untouched:
variance says how much the count wanders, and it wanders around a target that
now means something instead of being the whole answer.

The suppressed want is the Mamet half. `affect.normalize_wants` marks exactly
one want as suppressed -- the highest-urgency desire that conflicts with the
one being enacted -- and a mind sitting on one says less, not more.
"""

from __future__ import annotations

import pytest

from story.scene import DEFAULT_INTERACTION_CONFIG, dialogue_budget

CHAT = {"id": 1}
TURN = {"idx": 3}
BAND = {"min_lines": 0, "max_lines": 4, "variance": 0.0}


def _budget(monkeypatch, cfg=None, **kw):
    merged = dict(DEFAULT_INTERACTION_CONFIG)
    merged.update(BAND)
    merged.update(cfg or {})
    monkeypatch.setattr("story.scene.dialogue_config", lambda _cid: merged)
    return dialogue_budget(CHAT, TURN, 7, "n1", **kw)


class TestTheCardIsRead:
    def test_the_authored_voice_places_the_target_in_the_band(
            self, monkeypatch):
        """Three positions in the author's own band, not three numbers of
        their own: the band is the author's and this only says where in it
        this person sits."""
        terse = _budget(monkeypatch, verbosity="terse")["suggested_lines"]
        natural = _budget(monkeypatch, verbosity="natural")["suggested_lines"]
        chatty = _budget(monkeypatch, verbosity="chatty")["suggested_lines"]
        assert terse < natural < chatty

    @pytest.mark.parametrize("verbosity", ["", None, "garrulous"])
    def test_an_unset_or_unknown_voice_reads_as_the_middle(
            self, monkeypatch, verbosity):
        assert _budget(monkeypatch, verbosity=verbosity)["suggested_lines"] \
            == _budget(monkeypatch, verbosity="natural")["suggested_lines"]

    def test_the_authors_floor_outranks_the_quietest_card(self, monkeypatch):
        """An author who asked for two lines gets two out of the most
        laconic character they wrote."""
        budget = _budget(monkeypatch, cfg={"min_lines": 2, "max_lines": 5},
                         verbosity="terse", withholding=True)
        assert budget["suggested_lines"] >= 2
        assert budget["min_lines"] <= budget["suggested_lines"] \
            <= budget["hard_max"]


class TestTheBeatIsRead:
    def test_a_question_in_the_air_is_a_line_owed(self, monkeypatch):
        asked = _budget(monkeypatch, verbosity="natural",
                        awaiting_answer=True)["suggested_lines"]
        assert asked > _budget(monkeypatch,
                               verbosity="natural")["suggested_lines"]

    def test_a_suppressed_want_makes_them_say_less(self, monkeypatch):
        held = _budget(monkeypatch, verbosity="natural",
                       withholding=True)["suggested_lines"]
        assert held < _budget(monkeypatch,
                              verbosity="natural")["suggested_lines"]

    def test_the_two_can_answer_each_other(self, monkeypatch):
        """Asked something you do not want to answer: the beat is still
        yours to speak in, and the withholding is what shapes the line."""
        both = _budget(monkeypatch, verbosity="natural",
                       awaiting_answer=True, withholding=True)
        assert both["suggested_lines"] == _budget(
            monkeypatch, verbosity="natural")["suggested_lines"]


class TestTheAuthorsDialsSurvive:
    def test_variance_still_moves_the_count(self, monkeypatch):
        """The dial says how much the count wanders. It now wanders around
        the derived target rather than replacing it, so it must still be
        able to move the answer."""
        steady = {_budget(monkeypatch, cfg={"variance": 0.0},
                          verbosity="natural")["suggested_lines"]
                  for _ in range(8)}
        assert len(steady) == 1

        merged = dict(DEFAULT_INTERACTION_CONFIG)
        merged.update(BAND)
        merged["variance"] = 1.0
        monkeypatch.setattr("story.scene.dialogue_config", lambda _cid: merged)
        loose = {dialogue_budget(CHAT, TURN, 7, "n%d" % i,
                                 verbosity="natural")["suggested_lines"]
                 for i in range(24)}
        assert len(loose) > 1

    @pytest.mark.parametrize("nonce", [f"n{i}" for i in range(16)])
    def test_the_band_is_never_left(self, monkeypatch, nonce):
        merged = dict(DEFAULT_INTERACTION_CONFIG)
        merged.update({"min_lines": 1, "max_lines": 3, "variance": 1.0})
        monkeypatch.setattr("story.scene.dialogue_config", lambda _cid: merged)
        for kw in ({}, {"verbosity": "terse", "withholding": True},
                   {"verbosity": "chatty", "awaiting_answer": True}):
            budget = dialogue_budget(CHAT, TURN, 7, nonce, **kw)
            assert 1 <= budget["suggested_lines"] <= 3

    def test_the_same_beat_rerolls_to_the_same_number(self, monkeypatch):
        merged = dict(DEFAULT_INTERACTION_CONFIG)
        monkeypatch.setattr("story.scene.dialogue_config", lambda _cid: merged)
        again = [dialogue_budget(CHAT, TURN, 7, "n1", verbosity="chatty")
                 ["suggested_lines"] for _ in range(4)]
        assert len(set(again)) == 1
