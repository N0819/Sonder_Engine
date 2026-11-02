"""A creature authored without sight witnesses no act.

`charter_creature.normalize_creature` kept `range_rooms`, `hearing` and
`scent` and silently dropped every other sense, so an authored
`"sight": false` vanished, and `charter_observe` graded an `action` by sight
with no sense check. The descent's stalker -- "blind, deaf, indifferent to
vibration and light" -- acquired a `figure_action` claim for a knife drawn in
its room (audit world_charter_behaviours F3): the class fixed for hearing on
chat 117 turn 63, one sense over. A sense the card does not know is refused
with a notice rather than dropped."""
from world.charter import normalize_charter
from world.charter_creature import creature_warnings, normalize_creature
from world.charter_observe import plan_public_evidence


def _stalker(senses):
    return normalize_charter({
        "key": "stalker", "upkeeps": {}, "posts": {},
        "creature": {"senses": senses, "prey": ["figure"]},
        "bodies": {"it": {"place": "shaft"}}})


def _scene():
    return {"rooms": {"shaft": {"name": "Shaft", "adjacent": []}},
            "positions": {"Sarah Moon": "shaft"}, "entities": {}}


_ROWS = [{"source_id": "a1", "kind": "action", "actor": "Sarah Moon",
          "surface": "draws a knife", "visibility": "overt"}]


def test_an_authored_blind_creature_witnesses_no_action():
    plan = plan_public_evidence(
        _stalker({"hearing": False, "scent": True, "sight": False}),
        _ROWS, _scene(), 3, labels={"Sarah Moon": "the woman"})
    assert plan["inserts"] == []


def test_a_creature_with_eyes_still_sees():
    plan = plan_public_evidence(
        _stalker({"hearing": False, "scent": True, "sight": True}),
        _ROWS, _scene(), 3, labels={"Sarah Moon": "the woman"})
    assert any(claim.get("event_kind") == "figure_action"
               for _b, _s, claim in plan["inserts"])


def test_the_card_keeps_a_declared_blindness():
    senses = normalize_creature({"senses": {"sight": False}})["senses"]
    assert senses["sight"] is False


def test_a_sense_the_card_does_not_know_is_refused_with_a_notice():
    warnings = creature_warnings({"senses": {"echolocation": True}})
    assert any("echolocation" in w for w in warnings)
