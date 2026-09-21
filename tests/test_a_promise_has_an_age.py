"""A promise somebody made you is a fact with an age, and giving it up is a
decision.

The voice gate's `pending_act` records what a background figure still owes
(`still_owes` on its own reaction). It was written to be re-asked, so
`_valid_pending_act` goes quiet after `PENDING_ACT_BEATS` -- correctly, because
nagging a tapster forever is not what a tapster is. What nothing did was tell
the person WAITING, and an expiry is not an answer to them: the promise does
not stop existing when the engine stops nagging.

Measured, two_lives v7 (2026-09-19): Sal Weatherby asked an innkeeper for a
small ale on beat 6 and was told "Aye, in good time." The debt lapsed on beat
9. She stood braced against a timber post for the remaining 31 beats --
fourteen consecutive self-memories of shifting her weight and moving her gaze
-- and her one intention went dormant at beat 31. Nothing had told her that
half an hour of story time had passed with an ale unpoured.

Three rules hold this together:

  * ONE STORE. The debt is the figure's row; what the asker sees is derived
    from it (`owed_to`), because a debt written down twice is two debts free
    to disagree about whether it was kept.
  * AN AGE, NOT A VERDICT. The row says what and how long; asking again,
    catching an eye, complaining or walking out stays the character's.
  * ABANDONING IT IS AN ACT WITH A REASON. A ledger nobody can clear is a
    nag, and a thing you stopped expecting and a thing you forgot are
    different -- only the first is a decision.
"""

from __future__ import annotations

from persist.commit import (abandoned_debts, apply_abandoned_debts,
                            owed_service, owed_to)

ALE = {"what": "a small ale", "to": "the weathered woman",
       "to_ref": "Sal Weatherby", "turn": 6, "seconds": 300.0,
       "expires_turn": 9}


def _brewer(**over):
    row = dict(ALE)
    row.update(over)
    return {"name": "Goodfolk Simota Barleymaner", "pending_act": row}


class TestTheRowOutlivesTheNagging:
    def test_a_lapsed_promise_is_still_owed(self):
        """Beat 37, long past `expires_turn` 9: the gate has stopped asking
        and she is still waiting."""
        owed = owed_service(_brewer(), turn_idx=37, now_seconds=2100.0)
        assert owed["what"] == "a small ale"
        assert owed["lapsed"] is True
        assert owed["kept"] is False

    def test_it_is_measured_in_beats_and_in_story_time(self):
        owed = owed_service(_brewer(), turn_idx=37, now_seconds=2100.0)
        assert owed["beats"] == 31
        assert owed["seconds"] == 1800.0  # half an hour of fiction

    def test_the_gates_own_verdict_is_carried_not_restated(self):
        """`lapsed` comes from `_valid_pending_act`, so the two readers
        cannot disagree about when nagging stops."""
        assert owed_service(_brewer(), turn_idx=8)["lapsed"] is False
        assert owed_service(_brewer(), turn_idx=10)["lapsed"] is True

    def test_a_figure_owing_nothing_says_nothing(self):
        assert owed_service({"name": "Ostler"}) is None
        assert owed_service({"pending_act": {"what": "  "}}) is None


class TestTheAskerSeesItFromTheOtherSide:
    def test_the_person_waiting_is_told_what_and_by_whom(self):
        rows = owed_to("Sal Weatherby", {"p1": _brewer()}, 37, 2100.0)
        assert [r["what"] for r in rows] == ["a small ale"]
        assert rows[0]["from"] == "Goodfolk Simota Barleymaner"

    def test_nobody_else_is_told(self):
        assert owed_to("Emory Vane", {"p1": _brewer()}, 37, 2100.0) == []

    def test_it_matches_the_resolved_name_not_the_label(self):
        """`to` is the label that figure knows her by; `to_ref` is who she
        is. Matching on the label would make one mind's recognition decide
        another mind's ledger."""
        assert owed_to("the weathered woman", {"p1": _brewer()}, 37) == []
        assert owed_to("Sal Weatherby", {"p1": _brewer()}, 37)

    def test_oldest_first(self):
        rows = owed_to("Sal Weatherby",
                       {"a": _brewer(what="a mug", turn=20),
                        "b": _brewer(what="a small ale", turn=6)}, 37)
        assert [r["turn"] for r in rows] == [6, 20]


class TestGivingItUpIsADecision:
    def test_the_asker_can_close_it(self):
        presences = {"p1": _brewer()}
        cleared = apply_abandoned_debts(
            presences, {("goodfolk simota barleymaner", "a small ale"):
                        ("Sal Weatherby", "no ale is coming; the rain has set in")})
        assert [(c[0], c[3]) for c in cleared] == [
            ("Goodfolk Simota Barleymaner",
             "no ale is coming; the rain has set in")]
        assert "pending_act" not in presences["p1"]
        assert owed_to("Sal Weatherby", presences, 37) == []

    def test_abandoning_it_voids_it_for_the_figure_too(self):
        """An order a customer walked out on does not leave a tapster still
        holding a debt -- which is what it would mean if this only hid the
        row from the asker."""
        presences = {"p1": _brewer()}
        apply_abandoned_debts(presences, {
            ("goodfolk simota barleymaner", ""): ("Sal Weatherby", "leaving")})
        assert owed_service(presences["p1"], 37) is None

    def test_only_the_one_waiting_may_abandon_it(self):
        presences = {"p1": _brewer()}
        warned = []
        cleared = apply_abandoned_debts(
            presences, {("goodfolk simota barleymaner", "a small ale"):
                        ("Emory Vane", "not my business")},
            warn=warned.append)
        assert cleared == []
        assert presences["p1"]["pending_act"]["what"] == "a small ale"
        assert warned and "not to them" in warned[0]

    def test_a_reason_is_required(self):
        """Without one this is indistinguishable from forgetting, which the
        row already records by ageing."""

        class _Ctx:
            cast = [{"id": 1, "sheet": '{"identity":{"name":"Sal Weatherby"}}'}]
            character_results = {1: {"waiting_ops": [
                {"op": "abandon", "from": "Goodfolk Simota Barleymaner",
                 "what": "a small ale", "why": ""}]}}
            reaction_results = {}

        assert abandoned_debts(_Ctx()) == {}

    def test_a_declared_reason_reaches_the_applier(self):
        class _Ctx:
            cast = [{"id": 1, "sheet": '{"identity":{"name":"Sal Weatherby"}}'}]
            character_results = {1: {"waiting_ops": [
                {"op": "abandon", "from": "Goodfolk Simota Barleymaner",
                 "what": "a small ale", "why": "she has waited long enough"}]}}
            reaction_results = {}

        found = abandoned_debts(_Ctx())
        assert found[("goodfolk simota barleymaner", "a small ale")] == (
            "Sal Weatherby", "she has waited long enough")
