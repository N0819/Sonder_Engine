"""Ordinary evidence: the occasions that move a judgment without a disaster.

`RESEARCH.md` §1.7.6, design 2. The five-axis judgment network in
`world/charter_social.py` measured EMPTY across four charters of a real story
and across a simulated YEAR of the 40-body `twin_towns` fixture, because
judgments form only from witnessed events and every event kind the coarse
simulation emits is an institutional failure. Three producers were missing
outright: `report_confirmed`/`report_refuted` had weights, a WITNESSABLE entry
and runtime phrasing and no producer anywhere; `accusation` and `apology` had
weights and no producer because `quarrel` had no opener; and
`institution_order_executed` was emitted, witnessed and inert because the
signal table spelled it `order_obeyed`.

Measured on `twin_towns(40)`, window 4.0, seed 7, before and after:

  * healthy simulated year, off screen: 0 events, 0 judgment holders, both
    before and after. None of these producers fires in a working institution
    and THAT IS THE DESIGN.
  * famine simulated quarter, off screen: 6 judgment holders / 29 stances
    before, 40 holders / 149 stances after, with 130 of the surviving
    `reasons` citations naming `report_confirmed`.
  * famine simulated quarter, on screen: 0 accusations before (unreachable),
    14 after.
"""

from __future__ import annotations

import copy

from world.charter import (
    CHECKABLE, WITNESSABLE, check_reports, judgment_of, normalize_charter,
    opportunities, run, seed_needs, seed_roster, step,
    update_judgments_from_minds,
)
from world.charter_decide import (
    advance_decisions, deliver_orders, execute_orders)
from world.charter_news import news_claim, witness
from world.charter_runtime import _event_surface

from charter_worlds import twin_towns


def _road_charter(**bodies):
    """One upkeep at one place, and whoever the caller puts where."""
    return normalize_charter({
        "key": "road",
        "upkeeps": {"road_open": {
            "place": "crossing", "level": 0.9, "floor": 0.2,
            "drift_per_hour": 0.001, "service_per_hour": 0.03}},
        "posts": {"warden": {"place": "crossing", "serves": ["road_open"]}},
        "bodies": {key: dict(value) for key, value in bodies.items()},
    })


def _rumour(about="road_open", teller="oke", event_kind="upkeep_out_of_band",
            at_hours=8.0):
    """What one body was TOLD about a place, second-hand."""
    return {"kind": "news", "body": f"news:{event_kind}:{about}@{at_hours}",
            "event_kind": event_kind, "about": about, "actor": "",
            "place": "crossing", "happened_at": at_hours, "strength": 0.6,
            "as_of_hours": at_hours, "heard_from": teller}


class TestARumourIsSettledByLookingAtThePlace:
    """The one ordinary-evidence source in the package that is not a failure.
    Measured before it existed: a simulated quarter of the famine arm carried
    thousands of second-hand claims and not one of them was ever checked
    against the road they were about, because nothing in the repository
    produced `report_confirmed` or `report_refuted`."""

    def test_a_rumour_is_checked_against_the_place_you_are_standing_in(self):
        charter = _road_charter(
            hana={"place": "crossing"}, oke={"place": "crossing"})
        minds = {"hana": {"road_open@8.0": _rumour()}}

        minds, checks = check_reports(
            minds, charter["bodies"], charter["upkeeps"], 12.0)
        judgments, moved = update_judgments_from_minds({}, minds)

        assert checks == 1
        check = minds["hana"]["check:road_open@8.0:oke"]
        # The road is in band, so what she was told about it was not so.
        assert check["event_kind"] == "report_refuted"
        assert check["heard_from"] is None and check["strength"] == 1.0
        assert check["checked"] == "road_open@8.0"
        # And the conclusion is about the MOUTH, not the road.
        assert judgment_of(judgments, "hana", "oke")["trust"] < 0.0
        assert judgment_of(judgments, "hana", "road_open") is None

    def test_a_rumour_that_holds_up_is_evidence_for_the_teller(self):
        charter = _road_charter(
            hana={"place": "crossing"}, oke={"place": "crossing"})
        charter["upkeeps"]["road_open"]["level"] = 0.1
        minds = {"hana": {"road_open@8.0": _rumour()}}

        minds, checks = check_reports(
            minds, charter["bodies"], charter["upkeeps"], 12.0)
        judgments, _moved = update_judgments_from_minds({}, minds)

        assert checks == 1
        assert (minds["hana"]["check:road_open@8.0:oke"]["event_kind"]
                == "report_confirmed")
        assert judgment_of(judgments, "hana", "oke")["trust"] > 0.0

    def test_a_body_elsewhere_checks_nothing(self):
        """Co-location is the whole test, as it is for witnessing. A body that
        heard the road was out and is standing in the next town has settled
        nothing about anybody."""
        charter = _road_charter(
            hana={"place": "market"}, oke={"place": "crossing"})
        minds = {"hana": {"road_open@8.0": _rumour()}}

        minds, checks = check_reports(
            minds, charter["bodies"], charter["upkeeps"], 12.0)
        judgments, moved = update_judgments_from_minds({}, minds)

        assert checks == 0
        assert list(minds["hana"]) == ["road_open@8.0"]
        assert moved == []

    def test_a_firsthand_claim_judges_nobody(self):
        """A claim with no `heard_from` has no teller, so there is nobody to
        be right or wrong. Seeing the road yourself is not evidence about a
        person; it is just what you saw."""
        charter = _road_charter(hana={"place": "crossing"})
        minds = {"hana": {"road_open@8.0": _rumour(teller=None)}}

        minds, checks = check_reports(
            minds, charter["bodies"], charter["upkeeps"], 12.0)

        assert checks == 0
        assert list(minds["hana"]) == ["road_open@8.0"]

    def test_the_same_rumour_is_checked_once(self):
        """Two windows standing at the same crossing are one conclusion, not
        two. Idempotence through the stable `check:{claim}:{teller}` key and
        the judgment fold's existing `seen` guard, not a new ledger."""
        charter = _road_charter(
            hana={"place": "crossing"}, oke={"place": "crossing"})
        minds = {"hana": {"road_open@8.0": _rumour()}}

        minds, first = check_reports(
            minds, charter["bodies"], charter["upkeeps"], 12.0)
        judgments, _moved = update_judgments_from_minds({}, minds)
        settled = copy.deepcopy(judgment_of(judgments, "hana", "oke"))
        minds, second = check_reports(
            minds, charter["bodies"], charter["upkeeps"], 16.0)
        judgments, again = update_judgments_from_minds(judgments, minds)

        assert (first, second) == (1, 0)
        assert again == []
        assert judgment_of(judgments, "hana", "oke") == settled

    def test_a_check_is_private_to_the_holder(self):
        """A conclusion drawn from your own claim and your own feet is not an
        event. The room is full and nobody else's view of the teller moves --
        which is also why this producer costs no `scheduled_events` row."""
        charter = _road_charter(
            hana={"place": "crossing"}, oke={"place": "crossing"},
            bram={"place": "crossing"}, sena={"place": "crossing"})
        minds = {"hana": {"road_open@8.0": _rumour()},
                 "bram": {}, "sena": {}, "oke": {}}

        minds, checks = check_reports(
            minds, charter["bodies"], charter["upkeeps"], 12.0)
        judgments, _moved = update_judgments_from_minds({}, minds)

        assert checks == 1
        assert set(judgments) == {"hana"}
        assert minds["bram"] == {} and minds["sena"] == {}

    def test_only_a_place_is_checkable(self):
        """The allowlist is the firewall decision. A body's own state is not
        something a bystander reads off a room, and the institution's register
        is not in the room at all."""
        assert set(CHECKABLE) == {"upkeep_out_of_band", "upkeep_restored"}


class TestAnActBetweenTwoPeopleIsHeardByTheRoom:
    """`accuse` dropped regard and wrote `heard_blame`, `reconcile` raised it
    and closed the quarrel, and nobody else in the room ever learned either
    had happened."""

    def _town(self):
        charter = normalize_charter({
            "key": "town",
            "upkeeps": {"granary": {
                "place": "yard", "level": 0.9, "floor": 0.2,
                "drift_per_hour": 0.001, "service_per_hour": 0.03}},
            "posts": {"keeper": {"place": "yard", "serves": ["granary"]}},
            "bodies": {key: {"place": "yard"} for key in
                       ("ilse", "raul", "mira", "tomas")},
        })
        charter["roster"] = seed_roster(charter["bodies"])
        charter["needs"] = seed_needs(charter["bodies"])
        charter["active_places"] = ["yard"]
        # The register already holds somebody responsible. Everything that
        # follows is what the PEOPLE do with that, which until now was
        # nothing: `quarrel` had no opener but its own affordance.
        charter["politics"] = {"blame": {"raul": 2}}
        return charter

    def test_a_blame_that_has_landed_opens_a_quarrel(self):
        """`opportunities`' docstring has always named "a blame that has
        landed" as one of the three circumstances that open a situation, and
        it opened none. Measured: zero `accuse` acts in a simulated quarter of
        `twin_towns(40)` on screen and off, in health and in famine."""
        bodies = {key: {"key": key, "place": "yard", "available": True}
                  for key in ("ilse", "raul")}

        without = opportunities(bodies, {}, {}, (), {}, 8.0)
        withal = opportunities(bodies, {}, {}, (), {}, 8.0,
                               blame={"raul": 2})

        assert not [k for k in without if k.startswith("quarrel:")]
        assert [k for k in withal if k.startswith("quarrel:")] == [
            "quarrel:ilse:raul:raul"]

    def test_an_accusation_reaches_the_room_and_not_the_register(self):
        charter = self._town()

        after = charter
        events = []
        for index in range(6):
            after, produced = step(after, hours=4.0, seed=5 + index)
            events.extend(produced)

        spoken = [e for e in events if e["kind"] == "accusation"]
        assert spoken, "an accusation between two co-present bodies"
        event = spoken[0]
        # WHAT A BYSTANDER PERCEIVES, and nothing else. A payload field naming
        # the blame count -- or a surface phrase built from one -- would hand
        # the character tier the institution's own conclusion, because
        # `charter_runtime._scheduled_row` puts a WITNESSABLE kind's surface
        # onto the objective carrier rail.
        assert event["actor"] == event["body"] and event["subject"]
        assert set(event) == {
            "kind", "at_hours", "place", "about", "actor", "body", "subject"}
        assert "2" not in _event_surface(event)
        # Everybody standing there holds it, naming both parties.
        holders = [holder for holder, claims in after["minds"].items()
                   if any(c.get("event_kind") == "accusation"
                          for c in claims.values())]
        assert len(holders) >= 3
        claim = next(c for c in after["minds"][holders[0]].values()
                     if c.get("event_kind") == "accusation")
        assert claim["actor"] == event["actor"]
        assert claim["toward"] == event["subject"]

    def test_a_witness_learns_whom_the_act_was_directed_at(self):
        """`news_claim` builds a FIXED dict, and every payload key not in it
        is dropped -- which is why the existing `aid_given` event set
        `subject` and no witness ever received it. A body standing in the room
        saw who was helped as plainly as it saw who acted, so carrying it
        subtracts nothing."""
        event = {"kind": "aid_given", "at_hours": 8.0, "place": "yard",
                 "about": "ilse", "actor": "ilse", "body": "ilse",
                 "subject": "raul"}
        bodies = {"mira": {"place": "yard"}}

        minds, seen = witness({}, bodies, [event], 8.0)

        assert seen == 1
        assert next(iter(minds["mira"].values()))["toward"] == "raul"
        assert _event_surface(event) == "ilse gave aid to raul"

    def test_an_act_cannot_move_an_opinion_in_the_window_it_happens(self):
        """The lag is deliberate: nobody revises their view of a person in the
        instant they watch them act. `update_judgments_from_minds` runs before
        `enact`, so the claim lands this window and the stance forms next."""
        charter = self._town()

        first, produced = step(charter, hours=4.0, seed=5)

        assert [e for e in produced if e["kind"] == "accusation"]
        assert first["judgments"] == {}

        second, _produced = step(first, hours=4.0, seed=6)

        assert any("accusation" in [r["signal"] for r in stance["reasons"]]
                   for stances in second["judgments"].values()
                   for stance in stances.values())

    def test_both_speech_acts_are_witnessable_and_phrased(self):
        """A kind missing from any of the four dictionaries an event kind
        lives in is inert or renders as "changed state" -- the same class
        `aid_given` shipped in with weights, phrasing and no producer."""
        for kind, verb in (("accusation", "accused"),
                           ("apology", "made peace with")):
            event = {"kind": kind, "at_hours": 8.0, "place": "yard",
                     "about": "ilse", "actor": "ilse", "body": "ilse",
                     "subject": "raul"}
            assert kind in WITNESSABLE
            assert _event_surface(event) == f"ilse {verb} raul"
            claim = news_claim(event, 8.0)
            from world.charter_news import _native_news_phrase
            assert "changed at" not in _native_news_phrase(claim)


class TestAnOrderCarriedOutIsEvidenceAboutWhoCarriedItOut:
    """`institution_order_executed` has been emitted by `charter_decide` and
    witnessed into every co-present head since orders landed, and moved
    nothing: the signal table spelled the same happening `order_obeyed`."""

    def _executed(self, granary_stock):
        posts = {
            "storekeeper": {"place": "gate", "reports_to": "reeve",
                            "authority": []},
            "reeve": {"place": "gate", "reports_to": "",
                      "authority": ["release_stock"]},
        }
        bodies = {"alder": {"place": "gate", "available": True},
                  "ysra": {"place": "gate", "available": True}}
        watch = {"storekeeper": "alder", "reeve": "ysra"}
        minds = {"ysra": {"news:grain": {
            "kind": "news", "body": "news:grain", "event_kind": "stock_low",
            "about": "grain", "strength": 1.0, "heard_from": "alder"}}}
        decisions = {"policies": [{
            "when": "stock_low", "action": "release_stock",
            "from_post": "reeve", "to_post": "storekeeper", "priority": 2,
            "arguments": {"from_holder": "reserve", "to_holder": "granary",
                          "good": "grain", "quantity": 6},
        }]}
        economy = {"currency": "crowns",
                   "goods": {"grain": {"base_value": 2.0, "unit": "sack"}},
                   "stocks": {"granary": {"grain": 10},
                              "reserve": {"grain": granary_stock}}}

        decisions, _issued = advance_decisions(
            decisions, minds, watch, posts, bodies, charter_key="town",
            at_hours=12.0)
        decisions, _delivered = deliver_orders(decisions, watch, posts, bodies)
        decisions, economy, events = execute_orders(
            decisions, economy, at_hours=12.0, posts=posts)
        return bodies, events

    def test_an_order_carried_out_is_evidence_about_who_carried_it_out(self):
        bodies, events = self._executed(20)
        executed = [e for e in events
                    if e["kind"] == "institution_order_executed"]
        assert executed, "an order the institution actually carried out"

        minds, seen = witness({}, bodies, executed, 12.0)
        judgments, moved = update_judgments_from_minds({}, minds)

        assert seen >= 1
        # The order was received and carried out by the storekeeper, and the
        # reeve standing there saw it done. The end-to-end proof that the
        # vocabulary mismatch was the only thing wrong.
        assert executed[0]["by"] == "alder"
        assert judgment_of(judgments, "ysra", "alder")["respect"] > 0
        assert any(row["signal"] == "institution_order_executed"
                   for row in moved)

    def test_an_order_that_failed_for_want_of_stock_judges_nobody(self):
        """`institution_order_failed` fires on absent stock, carries no body
        at all, and records nobody refusing anything. Attributing it to
        `received_by` would blame a person for empty shelves."""
        bodies, events = self._executed(0)
        failed = [e for e in events
                  if e["kind"] == "institution_order_failed"]
        assert failed, "an order that could not be carried out"

        minds, _seen = witness({}, bodies, failed, 12.0)
        judgments, moved = update_judgments_from_minds({}, minds)

        assert moved == []
        assert judgments == {}


class TestOrdinaryEvidenceDoesNotPinAnAxis:
    """Judgments decay NOWHERE in this package, so every signal is permanent
    and `_clamp` saturates hard at 1.0. Measured on the 40-body `twin_towns`
    charter driven into famine for a simulated quarter, before the curve: 674
    `aid_given` events and 63 of 145 stance axes sitting at exactly 1.000 -- a
    network that had stopped carrying information and measured the same thing
    `served_beside` already measures."""

    def _aided(self, times):
        minds = {"mira": {}}
        for index in range(times):
            minds["mira"][f"news:aid:{index}"] = {
                "kind": "news", "body": f"news:aid:{index}",
                "event_kind": "aid_given", "about": "ilse", "actor": "ilse",
                "place": "yard", "happened_at": float(index), "strength": 1.0,
                "as_of_hours": float(index), "heard_from": None}
        judgments, _moved = update_judgments_from_minds({}, minds)
        return judgment_of(judgments, "mira", "ilse")

    def test_repeated_evidence_saturates_instead_of_pinning(self):
        thin, thick, relentless = (self._aided(3), self._aided(30),
                                   self._aided(400))

        assert thin["trust"] < thick["trust"] < relentless["trust"] < 1.0
        # And it still DISCRIMINATES over the range a story produces: the
        # fiftieth time somebody helps you is not worth what the first was.
        assert thick["trust"] - thin["trust"] > 0.5
        assert relentless["trust"] - thick["trust"] < 0.1

    def test_the_first_evidence_against_a_settled_view_lands_whole(self):
        """The deviation from "scale by ``1 - abs(before)``", and the reason
        for it: that form damps CONTRARY evidence just as hard, so in a
        package with no decay a settled stance could never come back."""
        settled = {"mira": {"ilse": dict(self._aided(400))}}
        betrayal = {"mira": {"news:harm:0": {
            "kind": "news", "body": "news:harm:0", "event_kind": "harm_done",
            "about": "ilse", "actor": "ilse", "place": "yard",
            "happened_at": 9.0, "strength": 1.0, "as_of_hours": 9.0,
            "heard_from": None}}}

        after, moved = update_judgments_from_minds(settled, betrayal)

        assert moved[0]["deltas"]["trust"] == -0.13


class TestTheQuietInstitutionStaysQuiet:
    """The property `TestAQuietWeekIsFree` pins, re-asserted after design 2.
    None of the new producers fires in a healthy institution and THAT IS THE
    DESIGN: a rumour is only checked where there are rumours, an accusation
    only where the register already blames somebody."""

    def test_a_quiet_quarter_still_emits_zero_events(self):
        """A simulated quarter here; the same fixture over a simulated YEAR
        measures 0 events and 0 judgment holders before and after design 2,
        and is left out of the suite only because it costs 17 seconds."""
        charter = normalize_charter(copy.deepcopy(twin_towns(folk=40)))
        charter["roster"] = seed_roster(charter["bodies"])
        charter["needs"] = seed_needs(charter["bodies"])
        charter["active_places"] = []

        after, events = run(charter, hours=2_190.0, window=4.0, seed=7)

        assert events == []
        assert after["judgments"] == {}
        assert not [claim for claims in after["minds"].values()
                    for key, claim in claims.items()
                    if key.startswith("check:")]

    def test_an_acquaintance_is_a_person_not_a_happening(self):
        """`minds` is ONE store with kinds in it, and the acquaintance writer
        read every key in it as somebody newly met. Measured on the famine arm
        of `twin_towns(40)` over a simulated quarter: 9,902 acquaintance rows,
        9,284 of which named a news key rather than a body -- forty-four per
        cent of the whole experience store spent on people who do not exist,
        evicting real rows under `EXPERIENCE_CAP`."""
        charter = normalize_charter({
            "key": "post",
            "upkeeps": {"lamp": {
                "place": "yard", "level": 0.9, "floor": 0.2,
                "drift_per_hour": 0.001, "service_per_hour": 0.03}},
            "posts": {"keeper": {"place": "yard", "serves": ["lamp"]}},
            "bodies": {"ilse": {"place": "yard"}, "raul": {"place": "yard"}},
        })
        charter["roster"] = seed_roster(charter["bodies"])
        charter["needs"] = seed_needs(charter["bodies"])
        charter["minds"] = {"ilse": {}}

        after, _events = step(charter, hours=4.0, seed=3)
        # Give ilse a piece of news the ordinary way, then advance again.
        after["minds"]["ilse"]["news:lamp@4"] = _rumour(
            about="lamp", teller="raul", at_hours=4.0)
        after, _events = step(after, hours=4.0, seed=4)

        met = [row for row in (after["experiences"].get("ilse") or ())
               if row["kind"] == "acquaintance"]
        assert met, "a body it actually met"
        assert all(row["other"] in after["bodies"] for row in met)
