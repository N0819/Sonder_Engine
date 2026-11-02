"""A person is addressed by institution AND key, and nothing re-spells either.

Two defects in the one identity rule "a charter body's dict key is permanent
identity" (audit world_charter_core F5, F6, both reproduced):

  * `person_id` joins `charter/body` and `_body_of` split on the FIRST "/",
    so a charter key carrying one -- the generator keeps the model's key, the
    editor saves any -- re-keyed every body on the first save/read round
    trip: `north/south ferry` + `cook:0001` came back as `south ferry/cook:0001`.
  * `transfer_person` took a bare body key, which the module itself says is
    not unique (two generated charters both mint `cook:0001`), lifted it from
    EVERY institution holding it and kept the last: Ada was erased and Bel
    moved. Re-employing a hermit left the hermit copy beside the employed one.
"""
import json

import pytest

from world.charter import normalize_charter
from world.charter_runtime import (_stored_shape, normalize_registry,
                                   transfer_person)


def _house(key, name):
    return normalize_charter({
        "key": key, "upkeeps": {}, "posts": {},
        "bodies": {"cook:0001": {"place": "kitchen", "name": name}}})


def _round_trip(registry):
    return normalize_registry(json.loads(json.dumps(_stored_shape(registry))))


def test_a_slash_in_a_charter_key_survives_the_round_trip():
    registry = normalize_registry({"items": {
        "north/south ferry": {"state": _house("north/south ferry", "Ada")}}})
    again = _round_trip(_round_trip(registry))
    bodies = again["items"]["north/south ferry"]["state"]["bodies"]
    assert list(bodies) == ["cook:0001"]
    assert bodies["cook:0001"]["name"] == "Ada"


def test_a_bare_key_two_institutions_share_is_refused():
    registry = normalize_registry({"items": {
        "inn": {"state": _house("inn", "Ada")},
        "tavern": {"state": _house("tavern", "Bel")},
        "market": {"state": normalize_charter(
            {"key": "market", "upkeeps": {}, "posts": {}, "bodies": {}})}}})
    with pytest.raises(ValueError, match="say which"):
        transfer_person(registry, "cook:0001", "market")
    assert registry["items"]["inn"]["state"]["bodies"]["cook:0001"]["name"] \
        == "Ada"
    assert registry["items"]["tavern"]["state"]["bodies"]["cook:0001"][
        "name"] == "Bel"


def test_the_institution_named_moves_exactly_its_own_person():
    registry = normalize_registry({"items": {
        "inn": {"state": _house("inn", "Ada")},
        "tavern": {"state": _house("tavern", "Bel")},
        "market": {"state": normalize_charter(
            {"key": "market", "upkeeps": {}, "posts": {}, "bodies": {}})}}})
    transfer_person(registry, "cook:0001", "market", from_charter="tavern")
    assert registry["items"]["inn"]["state"]["bodies"]["cook:0001"]["name"] \
        == "Ada"
    assert "cook:0001" not in registry["items"]["tavern"]["state"]["bodies"]
    assert registry["items"]["market"]["state"]["bodies"]["cook:0001"][
        "name"] == "Bel"


def test_a_hermit_employed_again_is_one_person_not_two():
    registry = normalize_registry({"items": {
        "inn": {"state": _house("inn", "Ada")},
        "market": {"state": normalize_charter(
            {"key": "market", "upkeeps": {}, "posts": {}, "bodies": {}})}}})
    transfer_person(registry, "cook:0001", None)
    assert "cook:0001" in registry["people"]
    transfer_person(registry, "cook:0001", "market")
    assert "cook:0001" not in registry["people"]
    again = _round_trip(registry)
    assert "cook:0001" not in again["people"]
    assert again["items"]["market"]["state"]["bodies"]["cook:0001"]["name"] \
        == "Ada"


def test_a_depart_op_names_the_house_the_shared_key_leaves():
    """`charter_ops`' `depart` names its charter, so a key two houses share
    is no ambiguity there: the tavern's Bel leaves, the inn's Ada stays."""
    from world.charter_ops import apply_charter_ops
    registry = normalize_registry({"items": {
        "inn": {"state": _house("inn", "Ada")},
        "tavern": {"state": _house("tavern", "Bel")},
        "market": {"state": normalize_charter(
            {"key": "market", "upkeeps": {}, "posts": {}, "bodies": {}})}}})
    apply_charter_ops(registry, [{"op": "depart", "charter": "tavern",
                                  "body": "cook:0001",
                                  "to_charter": "market"}])
    assert registry["items"]["inn"]["state"]["bodies"]["cook:0001"]["name"] \
        == "Ada"
    assert registry["items"]["market"]["state"]["bodies"]["cook:0001"][
        "name"] == "Bel"
