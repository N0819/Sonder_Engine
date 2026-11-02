"""The Director's raw charter op passes the same closed vocabulary the
Planner's does.

`apply_charter_ops` normalized an op only when its `op` was NOT already a
known kind -- and the Director's `state_diff.charter_ops` arrives raw with a
known kind, so its invented keys were silently ignored, the to/by
exclusivity and caps never held, and a `die` with no condition failed with a
bare `KeyError: 'condition'` that reached the Director as "'condition'"
(audit world_charter_behaviours F19). Normalizing is idempotent on an op the
Planner already normalized."""
import pytest

from world.charter import normalize_charter
from world.charter_ops import apply_charter_ops, normalize_charter_op
from world.charter_runtime import normalize_registry


def _registry(houses=("inn",)):
    items = {}
    for key in houses:
        state = normalize_charter({
            "key": key,
            "upkeeps": {"custom": {"place": "taproom", "level": 0.9,
                                   "floor": 0.2, "drift_per_hour": 0.0,
                                   "service_per_hour": 1.0}},
            "posts": {},
            "bodies": {"%s_hand" % key: {"place": "taproom",
                                         "name": "%s Hand" % key.title()}}})
        items[key] = {"state": state}
    return normalize_registry({"items": items})


def test_a_raw_die_with_no_condition_lands_as_dead():
    registry = _registry()
    apply_charter_ops(registry, [{"op": "die", "charter": "inn",
                                  "body": "inn_hand"}], by="director")
    body = registry["items"]["inn"]["state"]["bodies"]["inn_hand"]
    assert body["condition"] == "dead"


def test_a_raw_op_with_an_invented_key_is_refused_with_its_reason():
    registry = _registry()
    with pytest.raises(ValueError, match="does not take invented_key"):
        apply_charter_ops(registry, [{
            "op": "upkeep_fails", "charter": "inn", "upkeep": "custom",
            "to": 0.1, "invented_key": 1}], by="director")
    assert not registry["items"]["inn"]["state"].get("interventions")


def test_a_raw_op_saying_both_to_and_by_is_refused():
    registry = _registry()
    with pytest.raises(ValueError, match="not both"):
        apply_charter_ops(registry, [{
            "op": "upkeep_fails", "charter": "inn", "upkeep": "custom",
            "to": 0.1, "by": 0.2}], by="director")


def test_a_raw_op_with_no_charter_settles_it_from_the_body():
    registry = _registry(houses=("inn", "mill"))
    apply_charter_ops(registry, [{"op": "die", "body": "mill_hand"}],
                      by="director")
    body = registry["items"]["mill"]["state"]["bodies"]["mill_hand"]
    assert body["condition"] == "dead"


def test_an_op_the_planner_normalized_is_unchanged_by_a_second_pass():
    op = normalize_charter_op({"op": "upkeep_fails", "charter": "inn",
                               "upkeep": "custom", "by": 0.2})
    assert normalize_charter_op(dict(op)) == op
