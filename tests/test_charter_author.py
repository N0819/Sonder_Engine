"""The author-switch: §12a's claim, made falsifiable.

The claim: a voiced body never leaves the simulation — only its conduct is
authored for a stretch — and the machinery underneath must not be able to
tell which author moved it. The test of that is not a docstring, it is
bit-for-bit identity: a run in which every act a body chose is instead
AUTHORED (pinned to the same conduct) must produce the identical charter and
the identical events. If the two paths ever drift, that assertion is where
it shows first.

The other half is the licence: an authored act the state does not permit is
refused with a reason and changes nothing — the wardrobe lesson, applied to
conduct. Dropped with a notice, never applied, never silent.
"""

from __future__ import annotations

import copy

from world.charter import (
    REFUSED_NO_SITUATION, REFUSED_OUTSIDE_LICENCE, action_instances,
    authored, normalize_charter, seed_needs, seed_roster, step)

from charter_worlds import twin_towns


def _ready(folk=40, active=True):
    charter = normalize_charter(twin_towns(folk))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    if active:
        charter["active_places"] = sorted(
            {b["place"] for b in charter["bodies"].values()})
    return charter


def _small(figures=None):
    charter = normalize_charter({
        "key": "pair",
        "bodies": {
            "ash": {"competence": {}, "available": True, "place": "yard"},
            "birch": {"competence": {}, "available": True, "place": "yard"},
            "cedar": {"competence": {}, "available": True, "place": "loft"},
        },
        "figures": figures or {},
        "clock_hours": 10.0,
    })
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


class TestTheMachineryCannotTellWhichAuthor:
    def test_pinned_conduct_is_bit_for_bit_the_chosen_conduct(self):
        """Run A chooses; run B authors every one of run A's acts through
        `conduct`. Identical charters, identical events — there is no second
        apply-path to drift."""
        chosen, authored_arm = _ready(40), _ready(40)
        events_a, events_b = [], []
        for index in range(20):
            chosen, produced = step(chosen, hours=1.0, seed=index)
            events_a.extend(produced)
            conduct = {a["actor"]: {"act": a["act"], "other": a["other"]}
                       for a in chosen.get("acts") or []}
            authored_arm, produced = step(authored_arm, hours=1.0, seed=index,
                                          conduct=conduct)
            events_b.extend(produced)
            assert authored_arm.get("refused") == [], \
                "the state refused conduct it had itself chosen"

        assert events_a == events_b
        assert chosen == authored_arm

    def test_the_voiced_body_keeps_ticking(self):
        """Being on screen does not suspend hunger: a body whose conduct is
        authored every window still drains and recovers like any other."""
        charter = _small()
        charter["needs"]["ash"]["rest"]["level"] = 0.5
        before = copy.deepcopy(charter["needs"]["ash"])
        charter["active_places"] = ["yard"]
        for index in range(6):
            conduct = {"ash": {"act": "greet", "other": "birch"}}
            charter, _ = step(charter, hours=4.0, seed=index,
                              conduct=conduct)

        after = charter["needs"]["ash"]
        assert any(
            abs(float(after[n]["level"]) - float(before[n]["level"])) > 0.0
            for n in before), "authored conduct froze the body's needs"


class TestTheLicence:
    def test_an_act_outside_the_licence_is_refused_with_a_notice(self):
        """Authored conduct toward a body in another room: no situation
        licenses it, the refusal says so, and nothing changes."""
        charter = _small()
        charter["active_places"] = ["yard", "loft"]

        plain, _ = step(copy.deepcopy(charter), hours=4.0, seed=3)
        pinned, _ = step(copy.deepcopy(charter), hours=4.0, seed=3,
                         conduct={"ash": {"act": "greet", "other": "cedar"}})

        notices = pinned.get("refused")
        assert notices and notices[0]["actor"] == "ash"
        assert notices[0]["reason"] in (REFUSED_NO_SITUATION,
                                        REFUSED_OUTSIDE_LICENCE)
        # The refused arm did everything else identically -- ash simply did
        # not act, exactly as if it had chosen nothing.
        assert pinned["minds"].get("ash", {}).get("cedar") is None

        plain.pop("refused", None)
        pinned.pop("refused", None)
        plain_acts = [a for a in plain.pop("acts") if a["actor"] != "ash"]
        pinned_acts = [a for a in pinned.pop("acts") if a["actor"] != "ash"]
        assert plain_acts == pinned_acts

    def test_a_refused_authored_act_changes_nothing(self):
        charter = _small()

        after, record = authored(charter, "ash", "greet", "cedar")

        assert record["refused"] == REFUSED_NO_SITUATION
        assert after == normalize_charter(charter)


class TestAuthoredActsBetweenWindows:
    """`authored` is the per-beat API: a scene happens between planning
    windows, and each authored beat lands through the identical builders."""

    def test_an_authored_meeting_is_the_same_situation_a_window_opens(self):
        charter = _small()

        after, record = authored(charter, "ash", "greet", "birch")

        assert record["line"] == "ash greeted birch"
        assert after["minds"]["ash"]["birch"]["heard_from"] is None
        assert any(p["kind"] == "converse"
                   for p in after["practices"].values())

    def test_an_authored_tell_moves_a_real_claim(self):
        charter = _small()
        charter["minds"] = {
            "ash": {"story": {"body": "story", "competence": {},
                              "believed_available": True, "strength": 0.9,
                              "as_of_hours": 0.0, "heard_from": None},
                    "birch": {"body": "birch", "competence": {},
                              "believed_available": True, "strength": 1.0,
                              "as_of_hours": 0.0, "heard_from": None}}}

        after, record = authored(charter, "ash", "tell", "birch")

        assert "story" in record["line"]
        assert after["minds"]["birch"]["story"]["heard_from"] == "ash"


class TestFigureConduct:
    """The player's half of the seam: acts BY a figure touch only what a
    body could receive from them, and no figure ever grows a mind here."""

    def _with_figure(self):
        return _small(figures={"traveller": {"place": "yard",
                                             "surface": {"cloak": "grey"}}})

    def test_a_figure_greeting_is_seen_and_opens_the_situation(self):
        after, record = authored(self._with_figure(), "traveller", "greet",
                                 "ash")

        assert record["line"] == "traveller greeted ash"
        claim = after["minds"]["ash"]["traveller"]
        assert claim["kind"] == "figure" and claim["heard_from"] is None
        assert any(p["kind"] == "converse"
                   for p in after["practices"].values())
        assert "traveller" not in after["minds"]

    def test_a_figure_telling_lands_through_the_one_uptake_door(self):
        """Same retention, same regard, same stronger-holding-wins rule as a
        body-to-body telling -- the player cannot talk a body out of what it
        saw."""
        charter = self._with_figure()
        seen = {"body": "birch", "competence": {}, "believed_available": True,
                "strength": 1.0, "as_of_hours": 0.0, "heard_from": None}
        charter["minds"] = {"ash": {"birch": dict(seen)}}

        weaker = {"body": "birch", "competence": {},
                  "believed_available": False, "strength": 0.9}
        after, record = authored(charter, "traveller", "tell", "ash",
                                 claim=weaker)
        assert record["taken"] is False
        assert after["minds"]["ash"]["birch"]["believed_available"] is True

        fresh = {"body": "story", "competence": {},
                 "believed_available": True, "strength": 1.0}
        after, record = authored(charter, "traveller", "tell", "ash",
                                 claim=fresh)
        assert record["taken"] is True
        arrived = after["minds"]["ash"]["story"]
        assert arrived["heard_from"] == "traveller"
        assert arrived["strength"] < 1.0, "an authored telling arrived as " \
            "certainty a seeing would carry"

    def test_a_figure_accusation_reaches_the_accused(self):
        after, record = authored(self._with_figure(), "traveller", "accuse",
                                 "ash")

        assert "traveller" in after["heard_blame"]["ash"]
        assert any(p["kind"] == "quarrel"
                   for p in after["practices"].values())

    def test_a_figure_act_across_rooms_is_refused(self):
        after, record = authored(self._with_figure(), "traveller", "greet",
                                 "cedar")

        assert record["refused"] == REFUSED_OUTSIDE_LICENCE
        assert after == normalize_charter(self._with_figure())


class TestActionInstances:
    def test_a_bodys_options_include_the_figure_standing_there(self):
        charter = _small(figures={"traveller": {"place": "yard"}})
        charter, _ = authored(charter, "traveller", "greet", "ash")
        charter["minds"]["ash"]["extra"] = {
            "body": "extra", "competence": {}, "believed_available": True,
            "strength": 0.4, "as_of_hours": 0.0, "heard_from": None}

        rows = action_instances(charter, actor="ash")

        targets = {(r["act"], r["other"]) for r in rows.get("ash", ())}
        assert ("ask", "traveller") in targets or \
            ("tell", "traveller") in targets, \
            "no affordance targets the person actually standing there"
