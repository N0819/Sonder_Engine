"""A player's act toward a townsperson is answered by the townsperson's
own machinery.

The Harrowmere playtest (2026-09-02) recorded seven requests, two offers,
a promise and a handed letter aimed at Charter bodies, and
`charter_author.FIGURE_ACTS` carried none of them: the body answered in
prose the ledgers never saw. Each is now a class the engine already keeps
a ledger for -- an order, a favour and a bargain are commitments, a trade
is the economy, a gift is carriage -- so what the body says and what the
town records cannot diverge.
"""

from __future__ import annotations

import copy
import time

from world.charter import (
    REFUSED_OUTSIDE_LICENCE, authored, normalize_charter, seed_needs)
from world.charter_author import (
    ANSWERS, FAVOUR_REGARD_FLOOR, FIGURE_ACT_OF_SPEECH, FIGURE_ACTS,
    ORDER_REFUSAL_REGARD, acts_in_evidence, good_named, has_standing)
from world.charter_commitment import (
    OPEN_STATES, TERMINAL_STATES, answer_commitment, commitment_id,
    normalize_commitments, observe_public_commitments, open_commitment)
from world.charter_observe import apply_public_evidence, resolve_target_body
from world.charter_practice import _open_between


TRAVELLER = {"traveller": {"place": "yard", "surface": {"cloak": "grey"}}}


def _small(figures=None, **extra):
    charter = normalize_charter({
        "key": "pair",
        "bodies": {
            "ash": {"competence": {}, "available": True, "place": "yard"},
            "birch": {"competence": {}, "available": True, "place": "yard"},
            "cedar": {"competence": {}, "available": True, "place": "loft"},
        },
        "figures": figures or {},
        "clock_hours": 10.0,
        **extra,
    })
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def _ranked(**extra):
    """A chief in the yard whom the traveller rides, and a hand under them."""
    return _small(
        TRAVELLER,
        posts={"chief": {"place": "yard"},
               "hand": {"place": "yard", "reports_to": "chief"},
               "clerk": {"place": "yard", "reports_to": "hand"}},
        watch={"chief": "birch", "hand": "ash"},
        bindings={"birch": {"name": "traveller", "char_id": 1}},
        **extra)


def _market():
    return _small(TRAVELLER, economy={
        "goods": {"bread": {"label": "Barley Bread", "base_value": 1},
                  "fish": {"label": "River Fish", "base_value": 2}},
        "stocks": {"yard_stall": {"bread": 5}},
        "targets": {"yard_stall": {"fish": {"desired": 4}}},
        "markets": {"stall": {"place": "yard", "holder": "yard_stall"}},
    })


def _one(commitments):
    assert len(commitments) == 1
    return next(iter(commitments.values()))


class TestTheVocabulary:
    def test_the_six_dealings_are_figure_acts_and_the_answers_are_closed(self):
        for act in ("order", "request", "bargain", "promise", "trade", "give"):
            assert act in FIGURE_ACTS
        assert set(FIGURE_ACT_OF_SPEECH.values()) <= set(FIGURE_ACTS)
        assert "question" not in FIGURE_ACT_OF_SPEECH
        assert "greeting" not in FIGURE_ACT_OF_SPEECH
        assert 0.3 < ORDER_REFUSAL_REGARD < FAVOUR_REGARD_FLOOR <= 1.0
        for answer in ("obeyed", "refused", "granted", "declined",
                       "accepted", "heard", "quoted", "taken"):
            assert answer in ANSWERS


class TestOrder:
    def test_an_order_from_nobody_is_a_request(self):
        after, record = authored(_small(TRAVELLER), "traveller", "order",
                                 "ash", terms="fetch water", source_id="s1")
        assert record["as"] == "request"
        assert record["answer"] == "granted"
        assert _one(after["commitments"])["kind"] == "favour"

    def test_standing_reads_the_reports_to_chain_only(self):
        charter = _ranked()
        assert has_standing(charter, "traveller", "ash")
        # Two levels down the chain, still standing.
        charter["watch"]["clerk"] = "cedar"
        assert has_standing(charter, "traveller", "cedar")
        # Over the body the figure rides: no.
        assert not has_standing(charter, "traveller", "birch")
        # A self-report ends the chain rather than granting standing.
        charter["posts"]["hand"]["reports_to"] = "hand"
        assert not has_standing(charter, "traveller", "ash")
        # A stranger, riding nobody, has none.
        assert not has_standing(_small(TRAVELLER), "traveller", "ash")

    def test_a_standing_order_is_obeyed_as_an_accepted_commitment(self):
        after, record = authored(_ranked(), "traveller", "order", "ash",
                                 terms="fetch water", source_id="s1")
        assert record["answer"] == "obeyed" and "as" not in record
        held = _one(after["commitments"])
        assert held["kind"] == "order" and held["state"] == "accepted"
        assert held["promisor"] == "ash" and held["beneficiary"] == "traveller"
        assert held["recognized_by"] == ["ash"]

    def test_a_body_unable_to_stand_refuses_and_the_ledger_says_so(self):
        charter = _ranked()
        charter["bodies"]["ash"]["available"] = False
        after, record = authored(charter, "traveller", "order", "ash",
                                 terms="fetch water", source_id="s1")
        assert record["answer"] == "refused" and record["reason"] == "unable"
        assert _one(after["commitments"])["state"] == "repudiated"

    def test_contempt_refuses_a_superior(self):
        charter = _ranked()
        charter["politics"] = {"regard": {
            "ash->traveller": ORDER_REFUSAL_REGARD - 0.05}}
        _after, record = authored(charter, "traveller", "order", "ash",
                                  terms="fetch water", source_id="s1")
        assert record["answer"] == "refused" and record["reason"] == "regard"

    def test_a_member_acting_as_a_figure_carries_its_own_post(self):
        charter = _ranked()
        charter["figures"] = {}
        assert has_standing(charter, "birch", "ash")


class TestRequest:
    def test_an_unpressed_stranger_is_granted_and_owed(self):
        after, record = authored(_small(TRAVELLER), "traveller", "request",
                                 "ash", terms="a bed for the night",
                                 source_id="s1")
        assert record["answer"] == "granted"
        held = _one(after["commitments"])
        assert held["kind"] == "favour" and held["state"] == "accepted"
        # The body now READS itself as owing the traveller: the pair index
        # the affordances consult licenses it by key.
        assert _open_between(after["commitments"])["ash"]["traveller"][0] == 1

    def test_a_pressed_body_declines(self):
        charter = _small(TRAVELLER)
        need = next(iter(charter["needs"]["ash"].values()))
        need["level"] = float(need["floor"]) - 0.2
        _after, record = authored(charter, "traveller", "request", "ash",
                                  terms="a bed", source_id="s1")
        assert record["answer"] == "declined" and record["reason"] == "pressed"

    def test_low_regard_declines(self):
        charter = _small(TRAVELLER)
        charter["politics"] = {"regard": {
            "ash->traveller": FAVOUR_REGARD_FLOOR - 0.1}}
        _after, record = authored(charter, "traveller", "request", "ash",
                                  terms="a bed", source_id="s1")
        assert record["answer"] == "declined" and record["reason"] == "regard"

    def test_an_unsettled_debt_declines(self):
        charter = _small(TRAVELLER)
        charter["commitments"], _cid, _ = open_commitment(
            {}, source_id="p0", kind="promise", promisor="traveller",
            beneficiary="ash", terms="pay by Lammas", state="open")
        _after, record = authored(charter, "traveller", "request", "ash",
                                  terms="a bed", source_id="s1")
        assert record["answer"] == "declined"
        assert record["reason"] == "unsettled"

    def test_the_same_request_twice_is_one_record(self):
        charter = _small(TRAVELLER)
        after, _ = authored(charter, "traveller", "request", "ash",
                            terms="a bed", source_id="s1")
        again, record = authored(after, "traveller", "request", "ash",
                                 terms="a bed", source_id="s1")
        assert len(again["commitments"]) == 1
        assert record["commitment"] == _one(again["commitments"])["id"]


class TestBargainAndPromise:
    def test_a_bargain_is_the_figures_proposal_the_body_takes_up(self):
        after, record = authored(_small(TRAVELLER), "traveller", "bargain",
                                 "ash", terms="meals for work",
                                 source_id="s1")
        assert record["answer"] == "accepted"
        held = _one(after["commitments"])
        assert held["kind"] == "bargain" and held["state"] == "accepted"
        assert held["promisor"] == "traveller"

    def test_a_promise_opens_against_the_promisor_and_is_merely_heard(self):
        after, record = authored(_small(TRAVELLER), "traveller", "promise",
                                 "ash", terms="I'll come back",
                                 source_id="s1")
        assert record["answer"] == "heard"
        held = _one(after["commitments"])
        assert held["kind"] == "promise" and held["state"] == "open"
        assert held["promisor"] == "traveller"


class TestTrade:
    def test_a_price_is_quoted_and_the_deal_recorded(self):
        after, record = authored(_market(), "traveller", "trade", "ash",
                                 good="bread", quantity=2)
        assert record["answer"] == "quoted"
        assert record["quote"]["good"] == "bread"
        assert record["moved"] == 2.0 and record["deal"]["seller"] == \
            "yard_stall"
        assert after["economy"]["stocks"]["yard_stall"]["bread"] == 3.0
        assert after["economy"]["stocks"]["traveller"]["bread"] == 2.0
        assert after["economy"]["recent_trades"][-1]["reason"] == "sale"

    def test_no_market_here_refuses(self):
        charter = _market()
        charter["economy"]["markets"]["stall"]["place"] = "loft"
        after, record = authored(charter, "traveller", "trade", "ash",
                                 good="bread")
        assert record["refused"] == REFUSED_OUTSIDE_LICENCE
        assert record["reason"] == "no_market"
        assert after == normalize_charter(charter)

    def test_a_good_the_market_does_not_know_refuses(self):
        _after, record = authored(_market(), "traveller", "trade", "ash",
                                  good="silk")
        assert record["reason"] == "no_such_good"

    def test_an_empty_shelf_quotes_and_sells_nothing(self):
        after, record = authored(_market(), "traveller", "trade", "ash",
                                 good="fish")
        assert record["answer"] == "quoted" and record["moved"] == 0.0
        assert record["reason"] == "no_stock"
        assert "fish" not in (after["economy"]["stocks"].get("traveller")
                              or {})

    def test_regard_is_a_discount(self):
        dear = _market()
        dear["politics"] = {"regard": {"ash->traveller": 1.4}}
        cold = _market()
        cold["politics"] = {"regard": {"ash->traveller": 0.6}}
        _a, liked = authored(dear, "traveller", "trade", "ash", good="bread")
        _b, disliked = authored(cold, "traveller", "trade", "ash",
                                good="bread")
        assert liked["quote"]["unit_value"] < disliked["quote"]["unit_value"]


class TestGive:
    def test_a_gift_is_taken_and_is_aid_visibly_given(self):
        after, record = authored(_small(TRAVELLER), "traveller", "give",
                                 "ash", thing="sealed letter")
        assert record["answer"] == "taken"
        assert after["marks"]["ash"]["aided"]["by"] == "traveller"

    def test_nothing_given_is_refused(self):
        _after, record = authored(_small(TRAVELLER), "traveller", "give",
                                  "ash", thing="")
        assert record["refused"] == REFUSED_OUTSIDE_LICENCE


class TestTheLicenceStillHolds:
    def test_every_dealing_across_rooms_is_refused_and_changes_nothing(self):
        for act in ("order", "request", "bargain", "promise", "trade",
                    "give"):
            charter = _market()
            after, record = authored(charter, "traveller", act, "cedar",
                                     terms="x", thing="x", good="bread")
            assert record["refused"] == REFUSED_OUTSIDE_LICENCE, act
            assert after == normalize_charter(charter), act

    def test_a_dealing_warms_the_conversation(self):
        after, _ = authored(_small(TRAVELLER), "traveller", "request",
                            "ash", terms="a bed", source_id="s1")
        assert any(p["kind"] == "converse" and
                   set(p["roles"].values()) == {"ash", "traveller"}
                   for p in after["practices"].values())


class TestReadingTheBeat:
    def test_speech_kinds_map_and_the_rest_do_not(self):
        rows = acts_in_evidence([{
            "kind": "speech", "actor": "Wren", "target": "the clerk",
            "source_id": "speech:0",
            "speech_acts": [
                {"kind": "request", "content": "pull the rolls"},
                {"kind": "question", "content": "which rolls?"},
                {"kind": "command", "about": "the door"},
                {"kind": "offer", "content": "I'll pay"},
                {"kind": "promise", "content": "I'll return"},
                {"kind": "greeting"}]}], [], ["Wren"])
        assert [r["act"] for r in rows] == \
            ["request", "order", "bargain", "promise"]
        assert rows[0]["terms"] == "pull the rolls"
        assert rows[1]["terms"] == "the door"
        assert all(r["source_id"] == "speech:0" for r in rows)

    def test_only_a_figure_acts_and_only_toward_somebody(self):
        assert acts_in_evidence([{
            "kind": "speech", "actor": "the clerk", "target": "Wren",
            "speech_acts": [{"kind": "request", "content": "wait"}]}],
            [], ["Wren"]) == []
        assert acts_in_evidence([{
            "kind": "speech", "actor": "Wren", "target": "",
            "speech_acts": [{"kind": "request", "content": "wait"}]}],
            [], ["Wren"]) == []

    def test_a_transfer_from_a_figure_is_a_gift(self):
        rows = acts_in_evidence([], [
            {"op": "transfer", "object_id": "sealed_letter",
             "from_id": "Wren Ashby", "to_id": "reeve_halinham"},
            {"op": "transfer", "object_id": "coin",
             "from_id": "canvas_satchel", "to_id": "Wren Ashby"}],
            ["wren ashby"])
        assert len(rows) == 1
        assert rows[0]["act"] == "give" and rows[0]["thing"] == \
            "sealed letter"
        assert rows[0]["target"] == "reeve_halinham"

    def test_a_good_is_named_only_against_the_towns_own_table(self):
        economy = _market()["economy"]
        assert good_named(economy, "yard", "two loaves of barley bread") == \
            "bread"
        assert good_named(economy, "yard", "some fish") == "fish"
        assert good_named(economy, "yard", "bread and fish") == ""
        assert good_named(economy, "loft", "bread") == ""
        assert good_named(economy, "yard", "a room for the night") == ""


def _town():
    return normalize_charter({
        "key": "town",
        "bodies": {
            "reeve": {"name": "Halinham Nookfeller", "title": "Reeve",
                      "place": "hall"},
            "clerk_a": {"name": "Seleton Orrholmeer", "place": "hall"},
            "clerk_b": {"name": "Ambrin Vell", "place": "hall"},
            "porter": {"name": "Oren", "place": "yard"},
        },
        "posts": {"reeve": {"place": "hall"},
                  "clerk": {"place": "hall", "reports_to": "reeve"},
                  "clerk_2": {"place": "hall", "reports_to": "reeve"}},
        "watch": {"reeve": "reeve", "clerk": "clerk_a", "clerk_2": "clerk_b"},
    })


class TestResolvingTheTarget:
    def test_display_name_key_and_bare_name(self):
        town = _town()
        assert resolve_target_body(town, "Reeve Halinham Nookfeller",
                                   place="hall") == "reeve"
        assert resolve_target_body(town, "reeve", place="hall") == "reeve"
        assert resolve_target_body(town, "halinham nookfeller",
                                   place="hall") == "reeve"

    def test_a_slug_of_some_of_the_words_lands_on_the_one_body(self):
        assert resolve_target_body(_town(), "reeve_halinham",
                                   place="hall") == "reeve"
        assert resolve_target_body(_town(), "Nookfeller", place="hall") == \
            "reeve"

    def test_a_word_two_bodies_share_lands_on_neither(self):
        town = _town()
        town["bodies"]["clerk_b"]["name"] = "Seleton Vell"
        assert resolve_target_body(town, "seleton", place="hall") is None

    def test_place_scopes_and_a_bound_body_is_not_a_target(self):
        town = _town()
        assert resolve_target_body(town, "Oren", place="hall") is None
        assert resolve_target_body(town, "Oren", place="yard") == "porter"
        town["bindings"] = {"porter": {"name": "Oren", "char_id": 3}}
        assert resolve_target_body(town, "Oren", place="yard") is None

    def test_an_entity_the_identity_floor_bound_resolves_by_its_ref(self):
        scene = {"entities": {"reeve_clerk": {
            "name": "the reeve's clerk", "kind": "person",
            "aliases": ["clerk"],
            "charter_ref": {"charter": "town", "body": "clerk_a"}}}}
        assert resolve_target_body(_town(), "reeve_clerk", place="hall",
                                   scene=scene) == "clerk_a"
        assert resolve_target_body(_town(), "reeve_clerk",
                                   place="hall") is None


class TestTheCommitmentDoor:
    def test_a_promise_to_a_spelling_is_owed_to_the_body(self):
        speech = {
            "source_id": "speech:0", "kind": "speech", "actor": "Rowan",
            "target": "Reeve Ysra", "exact_quote": '"I will return."',
            "speech_acts": [{"kind": "promise", "content": "I will return."}]}
        loose, _ = observe_public_commitments(
            {}, [speech], {"speech:0": ["reeve"]})
        assert _one(loose)["beneficiary"] == "Reeve Ysra"
        assert "reeve" not in _open_between(loose)
        keyed, _ = observe_public_commitments(
            {}, [speech], {"speech:0": ["reeve"]},
            targets={"speech:0": "reeve"})
        assert _one(keyed)["beneficiary"] == "reeve"
        assert _open_between(keyed)["reeve"]["Rowan"] == (0, 1)

    def test_apply_public_evidence_resolves_the_target_for_the_door(self):
        charter = normalize_charter({
            "key": "town",
            "bodies": {"reeve": {"name": "Ysra", "title": "Reeve",
                                 "place": "hall"}}})
        scene = {"rooms": {"hall": {"name": "Hall", "adjacent": []}},
                 "positions": {"Rowan": "hall"}}
        speech = {
            "source_id": "speech:0", "kind": "speech", "actor": "Rowan",
            "target": "Reeve Ysra", "exact_quote": '"I will return."',
            "volume": "normal", "visibility": "overt", "conceal_from": [],
            "speech_acts": [{"kind": "promise", "content": "I will return."}]}
        after, _metrics = apply_public_evidence(charter, [speech], scene, 3)
        assert _one(after["commitments"])["beneficiary"] == "reeve"

    def test_the_act_and_the_utterance_are_one_record(self):
        """A promise arrives twice per beat -- as evidence and as an act --
        and keys on the same four facts, so it is one undertaking."""
        charter = _small(TRAVELLER)
        speech = {
            "source_id": "speech:0", "kind": "speech", "actor": "traveller",
            "target": "ash", "exact_quote": '"I will return."',
            "speech_acts": [{"kind": "promise", "content": "I will return."}]}
        charter["commitments"], _ = observe_public_commitments(
            {}, [speech], {"speech:0": ["ash"]},
            targets={"speech:0": "ash"})
        after, record = authored(charter, "traveller", "promise", "ash",
                                 terms="I will return.",
                                 source_id="speech:0")
        assert len(after["commitments"]) == 1
        assert record["commitment"] == commitment_id(
            "speech:0", "traveller", "ash", "I will return.")

    def test_answering_accepts_only_a_proposal_and_refuses_any_open_one(self):
        held, cid, opened = open_commitment(
            {}, source_id="s", kind="favour", promisor="ash",
            beneficiary="traveller", terms="a bed", state="proposed")
        assert opened
        taken, changed = answer_commitment(held, cid, accepted=True, by="ash")
        assert changed and taken[cid]["state"] == "accepted"
        again, changed = answer_commitment(taken, cid, accepted=True, by="ash")
        assert not changed
        refused, changed = answer_commitment(taken, cid, accepted=False,
                                             by="ash", note="pressed")
        assert changed and refused[cid]["state"] == "repudiated"
        assert refused[cid]["lifecycle"][-1]["note"] == "pressed"
        done, changed = answer_commitment(refused, cid, accepted=False,
                                          by="ash")
        assert not changed and done[cid]["state"] in TERMINAL_STATES

    def test_reopening_an_existing_record_only_widens_recognition(self):
        held, cid, _ = open_commitment(
            {}, source_id="s", kind="favour", promisor="ash",
            beneficiary="traveller", terms="a bed", state="proposed",
            recognized_by=["ash"])
        held, _ = answer_commitment(held, cid, accepted=True, by="ash")
        again, same, opened = open_commitment(
            held, source_id="s", kind="favour", promisor="ash",
            beneficiary="traveller", terms="a bed", state="proposed",
            recognized_by=["birch"])
        assert same == cid and not opened
        assert again[cid]["state"] == "accepted"
        assert again[cid]["recognized_by"] == ["ash", "birch"]
        assert normalize_commitments(again) == again
        assert again[cid]["state"] in OPEN_STATES


def _scene():
    return {
        "rooms": {"hall": {"name": "Hall", "adjacent": []},
                  "yard": {"name": "Yard", "adjacent": []}},
        "positions": {"Wren Ashby": "hall"},
    }


def _hall_charter():
    return normalize_charter({
        "key": "town",
        "bodies": {
            "reeve": {"name": "Halinham Nookfeller", "title": "Reeve",
                      "place": "hall"},
            "clerk": {"name": "Seleton Orrholmeer", "place": "hall"},
            "porter": {"name": "Oren", "place": "yard"},
        },
        "posts": {"reeve": {"place": "hall"},
                  "clerk": {"place": "hall", "reports_to": "reeve"},
                  "stall": {"place": "hall"}},
        "watch": {"reeve": "reeve", "clerk": "clerk"},
        "economy": {
            "goods": {"bread": {"label": "Barley Bread", "base_value": 1}},
            "stocks": {"hall_stall": {"bread": 4}},
            "markets": {"stall": {"place": "hall", "holder": "hall_stall"}},
        },
    })


def _request(target="the clerk", content="pull the old rolls", kind="request"):
    return {
        "source_id": "speech:0", "kind": "speech", "actor": "Wren Ashby",
        "exact_quote": '"%s"' % content, "target": target, "volume": "normal",
        "visibility": "overt", "conceal_from": [], "salience": 0.8,
        "speech_acts": [{"kind": kind, "content": content}],
    }


class TestPlanningAgainstTheRegistry:
    def test_a_request_to_a_spelling_is_planned_onto_the_one_body(self):
        from world.charter_runtime import plan_figure_acts

        plans = plan_figure_acts(
            {"items": {"town": {"state": _hall_charter()}}},
            [_request("Seleton")], [], _scene(), ["Wren Ashby"])
        assert [(p["body"], p["act"]) for p in plans] == \
            [("clerk", "request")]
        assert plans[0]["room"] == "hall"

    def test_an_offer_naming_a_good_sold_here_is_a_trade(self):
        from world.charter_runtime import plan_figure_acts

        plans = plan_figure_acts(
            {"items": {"town": {"state": _hall_charter()}}},
            [_request("Seleton", "a loaf of barley bread, please", "offer")],
            [], _scene(), ["Wren Ashby"])
        assert plans[0]["act"] == "trade" and plans[0]["good"] == "bread"

    def test_a_figure_the_scene_does_not_stand_plans_nothing(self):
        from world.charter_runtime import plan_figure_acts

        scene = _scene()
        scene["positions"] = {}
        assert plan_figure_acts(
            {"items": {"town": {"state": _hall_charter()}}},
            [_request("Seleton")], [], scene, ["Wren Ashby"]) == []

    def test_two_charters_both_claiming_the_name_plan_nothing(self):
        from world.charter_runtime import plan_figure_acts

        other = _hall_charter()
        other["key"] = "guild"
        assert plan_figure_acts(
            {"items": {"town": {"state": _hall_charter()},
                       "guild": {"state": other}}},
            [_request("Seleton")], [], _scene(), ["Wren Ashby"]) == []

    def test_a_gift_lands_by_the_directors_slug(self):
        from world.charter_runtime import apply_figure_acts, plan_figure_acts

        registry = {"items": {"town": {"state": _hall_charter()}}}
        plans = plan_figure_acts(
            registry, [],
            [{"op": "transfer", "object_id": "sealed_letter",
              "from_id": "Wren Ashby", "to_id": "reeve_halinham",
              "relation": "held"}],
            _scene(), ["Wren Ashby"])
        assert plans[0]["body"] == "reeve" and plans[0]["act"] == "give"
        state, records = apply_figure_acts(
            copy.deepcopy(registry["items"]["town"]["state"]), plans, "town")
        assert records[0]["answer"] == "taken"
        assert "Wren Ashby" not in state["figures"], \
            "a figure survived the act"
        assert state["marks"]["reeve"]["aided"]["by"] == "Wren Ashby"


class TestTheCommitAndTheVoice:
    def test_the_act_rides_the_evidence_write_and_the_voice_previews_it(
            self, temp_db, monkeypatch):
        from world import charter_runtime

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Figure acts", "", time.time()))
        charter_runtime.save_registry(cid, {"town": _hall_charter()})
        writes = []
        original = charter_runtime.save_registry

        def counted(*args, **kwargs):
            writes.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(charter_runtime, "save_registry", counted)

        # The voice, BEFORE the commit: the answer is previewed by the same
        # plan, on a copy, and carries no name of the asker.
        view = charter_runtime.presence_view(
            cid, "hall", "Seleton Orrholmeer", evidence=[_request("Seleton")],
            inventory_ops=[], scene=_scene(), actors=["Wren Ashby"])
        assert view[0]["answers"] == [{
            "act": "request", "terms": "pull the old rolls",
            "answer": "granted"}]
        stored = charter_runtime.registry_for(cid)["items"]["town"]["state"]
        assert stored["commitments"] == {}, "a preview wrote the ledger"

        result = charter_runtime.ingest_public_evidence(
            cid, [_request("Seleton")], _scene(), turn_id=7,
            inventory_ops=[], figures=["Wren Ashby"])
        assert result["acquired"] == 2   # the reeve heard it too
        assert [r["answer"] for r in result["figure_acts"]] == ["granted"]
        assert len(writes) == 1
        held = charter_runtime.registry_for(cid)["items"]["town"]["state"]
        favour = _one(held["commitments"])
        assert favour["promisor"] == "clerk" and favour["state"] == "accepted"
        # And the body's own slice shows what it owes.
        later = charter_runtime.presence_view(
            cid, "hall", "Seleton Orrholmeer", figures=["Wren Ashby"])
        assert later[0]["presence"]["commitments"][0]["id"] == favour["id"]

    def test_a_gift_with_no_speech_still_lands_in_one_write(self, temp_db):
        from world import charter_runtime

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Figure gift", "", time.time()))
        charter_runtime.save_registry(cid, {"town": _hall_charter()})
        result = charter_runtime.ingest_public_evidence(
            cid, [], _scene(), turn_id=7,
            inventory_ops=[{"op": "transfer", "object_id": "sealed_letter",
                            "from_id": "Wren Ashby",
                            "to_id": "reeve_halinham"}],
            figures=["Wren Ashby"])
        assert result["figure_acts"][0]["answer"] == "taken"
        held = charter_runtime.registry_for(cid)["items"]["town"]["state"]
        assert held["marks"]["reeve"]["aided"]["by"] == "Wren Ashby"

    def test_a_beat_with_nothing_aimed_at_anyone_is_as_before(self, temp_db):
        from world import charter_runtime

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Figure quiet", "", time.time()))
        charter_runtime.save_registry(cid, {"town": _hall_charter()})
        assert charter_runtime.ingest_public_evidence(
            cid, [], _scene(), turn_id=7, inventory_ops=[],
            figures=["Wren Ashby"]) == {
                "sources": 0, "opportunities": 0, "acquired": 0}
