"""Compact seams for Charter judgment, commitments, trade and decisions.

Full multi-month realism audits belong in tools.  These tests prove that the
mechanisms work, remain local, and compose without a provider call.
"""

from world.charter import (
    advance_decisions, advance_economy, commitment_view, deliver_orders,
    execute_orders, judgment_of, normalize_charter, quote, stock_band,
    update_judgments_from_minds)
from world.charter_observe import apply_public_evidence


def _evidence(kind="threat", source="sp:1"):
    return {
        "source_id": source, "kind": "speech", "actor": "Traveller",
        "target": "Guard", "exact_quote": "Leave before dusk",
        "volume": "normal", "visibility": "overt", "conceal_from": [],
        "speech_acts": [{"kind": kind, "content": "Leave before dusk"}],
        "salience": 0.8,
    }


def _scene():
    return {
        "rooms": {"gate": {"name": "Gate", "adjacent": []},
                  "office": {"name": "Office", "adjacent": []}},
        "positions": {"Traveller": "gate", "Guard": "gate"},
    }


def test_only_the_hearer_forms_a_local_judgment():
    charter = normalize_charter({
        "key": "watch",
        "bodies": {"guard": {"place": "gate"},
                   "clerk": {"place": "office"}},
    })

    after, metrics = apply_public_evidence(
        charter, [_evidence()], _scene(), turn_id=4)

    guard = judgment_of(after["judgments"], "guard", "Traveller")
    assert guard["fear"] > 0
    assert guard["suspicion"] > 0
    assert judgment_of(after["judgments"], "clerk", "Traveller") is None
    assert metrics["judgments_moved"] == 1
    assert guard["reasons"][0]["evidence_id"] == "scene:4:sp:1"


def test_a_promise_is_recognized_only_by_people_who_heard_it():
    charter = normalize_charter({
        "key": "watch",
        "bodies": {"guard": {"place": "gate"},
                   "clerk": {"place": "office"}},
    })
    promise = _evidence("promise", "sp:promise")
    promise["exact_quote"] = "I will bring grain tomorrow"
    promise["speech_acts"] = [{
        "kind": "promise", "content": "bring grain tomorrow"}]

    after, metrics = apply_public_evidence(
        charter, [promise], _scene(), turn_id=5)

    held = commitment_view(after["commitments"], "guard")
    assert len(held) == 1
    assert held[0]["promisor"] == "Traveller"
    assert held[0]["terms"] == "bring grain tomorrow"
    assert held[0]["state"] == "open"
    assert commitment_view(after["commitments"], "clerk") == []
    assert metrics["commitments_opened"] == 1


def _economy():
    return {
        "currency": "crowns",
        "goods": {"grain": {"base_value": 2.0, "unit": "sack"}},
        "stocks": {"granary": {"grain": 10}, "reserve": {"grain": 20}},
        "targets": {
            "granary": {"grain": {"minimum": 8, "desired": 16,
                                   "capacity": 30}},
            "reserve": {"grain": {"minimum": 5, "desired": 15,
                                  "capacity": 30}},
        },
        "flows": {"meals": {"holder": "granary", "good": "grain",
                              "kind": "consume", "lots_per_hour": 1}},
        "markets": {"square": {"place": "gate", "holder": "granary",
                                "margin": 0.1, "route_burden": 0.5}},
    }


def test_scarcity_changes_stock_band_and_route_sensitive_price():
    before = quote(_economy(), "square", "grain")
    after, events = advance_economy(_economy(), 4.0, at_hours=10.0)
    after_quote = quote(after, "square", "grain")

    assert stock_band(after, "granary", "grain") == "low"
    assert [event["kind"] for event in events] == ["stock_low"]
    assert after_quote["unit_value"] > before["unit_value"]
    assert after_quote["currency"] == "crowns"


def test_a_report_reaches_a_leader_then_an_order_moves_down_and_moves_stock():
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
        "about": "grain", "strength": 1.0, "heard_from": "Alder"}}}
    decisions = {"policies": [{
        "when": "stock_low", "action": "release_stock",
        "from_post": "reeve", "to_post": "storekeeper", "priority": 2,
        "arguments": {"from_holder": "reserve", "to_holder": "granary",
                      "good": "grain", "quantity": 6},
    }]}

    decisions, issued = advance_decisions(
        decisions, minds, watch, posts, bodies, charter_key="town",
        at_hours=12.0)
    decisions, delivered = deliver_orders(decisions, watch, posts, bodies)
    decisions, economy, events = execute_orders(
        decisions, _economy(), at_hours=12.0, posts=posts)

    assert len(issued) == len(delivered) == 1
    assert decisions["orders"][0]["status"] == "executed"
    assert economy["stocks"]["granary"]["grain"] == 16
    assert any(event["kind"] == "goods_exchanged" for event in events)


def test_hearsay_is_weaker_and_idempotent():
    claim = {
        "kind": "news", "body": "e:1", "event_kind": "figure_speech",
        "strength": 1.0, "heard_from": "Miller",
        "public_evidence": {"actor": "Traveller",
                            "speech_acts": [{"kind": "threat"}]},
    }
    first, moved = update_judgments_from_minds({}, {"guard": {"e:1": claim}})
    second, repeated = update_judgments_from_minds(
        first, {"guard": {"e:1": claim}})

    assert len(moved) == 1
    assert repeated == []
    assert judgment_of(second, "guard", "Traveller")["fear"] < 0.16
