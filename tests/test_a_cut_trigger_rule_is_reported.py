"""A trigger rule or consequence the caps cut is reported, and a shipped
default is never cut to make room for an authored row.

`_normalize_rule` sliced `then` to `TRIGGER_THEN_CAP` and `normalize_triggers`
sorted every rule by id and kept the first `TRIGGER_CAP` -- both silently, the
exact failure `trigger_warnings` exists to prevent ("a rule that silently does
nothing is the empty-psychology-field failure"). Measured (audit
world_charter_generation_run F11): a four-op rule kept three with no warning,
and 32 authored rules `a00`-`a31` evicted the shipped `blame_opens_a_quarrel`
because it sorts after them. The caps stay the owner's."""
from world.charter_trigger import (DEFAULT_TRIGGERS, TRIGGER_CAP,
                                   TRIGGER_THEN_CAP, normalize_triggers,
                                   trigger_warnings)


def _emit(kind="aid_given"):
    return {"op": "emit", "kind": kind, "actor": "actor", "subject": "subject"}


def test_a_consequence_past_the_cap_is_reported_and_the_rest_still_run():
    rule = {"id": "busy", "on": "act:accuse",
            "then": [_emit() for _ in range(TRIGGER_THEN_CAP + 1)]}
    rows = {row["id"]: row for row in normalize_triggers([rule])}
    assert len(rows["busy"]["then"]) == TRIGGER_THEN_CAP
    assert not rows["busy"].get("refused"), "the rule still runs"
    assert any(w.startswith("busy:") for w in trigger_warnings([rule]))


def test_a_full_rulebase_keeps_the_shipped_default_and_reports_the_cut():
    authored = [{"id": "a%02d" % i, "on": "act:accuse", "then": [_emit()]}
                for i in range(TRIGGER_CAP)]
    kept = {row["id"] for row in normalize_triggers(authored)}
    for default in DEFAULT_TRIGGERS:
        assert default["id"] in kept
    assert len(kept) <= TRIGGER_CAP
    cut = [w for w in trigger_warnings(authored)
           if w.split(":", 1)[0] not in kept]
    assert cut, "every rule the cap dropped is named"


def test_an_authored_override_of_a_default_keeps_its_slot():
    override = {"id": DEFAULT_TRIGGERS[0]["id"], "on": "blame_landed",
                "then": []}
    rows = {row["id"]: row for row in normalize_triggers([override])}
    assert rows[DEFAULT_TRIGGERS[0]["id"]]["then"] == []


def test_the_authoring_surface_reports_what_the_caps_cut():
    """`registry_warnings` normalizes the registry before it reads it, and
    normalization is what truncates: it reads the rules as WRITTEN."""
    from world.charter_runtime import registry_warnings
    authored = [{"id": "a%02d" % i, "on": "act:accuse", "then": [_emit()]}
                for i in range(TRIGGER_CAP)]
    authored.append({"id": "busy", "on": "act:accuse",
                     "then": [_emit() for _ in range(TRIGGER_THEN_CAP + 1)]})
    state = {"key": "inn", "upkeeps": {}, "posts": {},
             "bodies": {"tam": {"place": "yard"}}, "triggers": authored}
    warnings = registry_warnings({"items": {"inn": {"state": state}}})
    assert any("TRIGGER_CAP" in w and "not loaded" in w for w in warnings)
