"""At the intervention cap a new row is refused; a scheduled END never goes.

`normalize_interventions` sorted the rows and kept the first
`INTERVENTION_CAP`, so at the cap the row scheduled LATEST was dropped --
and the latest rows are exactly the `:stand_down` and `:revert` ends other
ops schedule. Measured (audit world_charter_behaviours F8): a called watch
whose stand-down was evicted by one more authored shock stood for ever, its
`guard:<place>` upkeep first in `priority`, pulling crew off every ordinary
post. The cap stays the owner's; what it refuses is the newcomer, visibly."""
from world.charter import normalize_charter
from world.charter_intervene import (INTERVENTION_CAP, apply_due,
                                     intervention_warnings,
                                     normalize_interventions)


def _charter():
    return normalize_charter({
        "key": "gate",
        "upkeeps": {"custom": {"place": "yard", "level": 1.0, "floor": 0.2,
                               "drift_per_hour": 0.0,
                               "service_per_hour": 1.0}},
        "posts": {}, "bodies": {"tam": {"place": "yard"}}})


def _far_rows(count):
    # Future authored shocks, all due BEFORE the watch would stand down, so
    # its stand-down is the latest row scheduled -- the row a sort-and-keep
    # cap evicts.
    return [{"id": "far:%03d" % i, "op": "upkeep_shock", "upkeep": "custom",
             "delta": -0.01, "at_hours": 2.0 + 0.5 * i} for i in range(count)]


def test_a_watch_called_into_a_full_schedule_still_stands_down():
    charter = _charter()
    charter["interventions"] = _far_rows(INTERVENTION_CAP - 1) + [
        {"id": "call", "op": "watch_shock", "place": "yard", "crew": 1,
         "at_hours": 0.0, "until_hours": 48.0}]
    charter, _events = apply_due(charter, 1.0)
    assert "yard" in charter["mobilisations"]
    ids = [row["id"] for row in charter["interventions"]]
    assert "call:stand_down" in ids
    # One more authored row lands on a full schedule.
    charter["interventions"] = normalize_interventions(
        list(charter["interventions"]) + [
            {"id": "late", "op": "upkeep_shock", "upkeep": "custom",
             "delta": -0.1, "at_hours": 2.0}])
    ids = [row["id"] for row in charter["interventions"]
           if not row.get("refused")]
    assert "call:stand_down" in ids
    assert len(ids) <= INTERVENTION_CAP
    refused = [row for row in charter["interventions"] if row.get("refused")]
    assert [row["id"] for row in refused] == ["late"]
    # ...and the stand-down then lands: the watch does not stand for ever.
    charter, events = apply_due(charter, 60.0)
    assert "yard" not in (charter.get("mobilisations") or {})
    assert any(e["kind"] == "mobilisation_lapsed" for e in events)


def test_the_refusal_is_a_notice_the_author_can_read():
    rows = _far_rows(INTERVENTION_CAP) + [
        {"id": "extra", "op": "upkeep_shock", "upkeep": "custom",
         "delta": -0.1, "at_hours": 1.0}]
    warnings = intervention_warnings(rows)
    assert any(w.startswith("extra:") for w in warnings)
