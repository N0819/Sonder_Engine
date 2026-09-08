"""A29 (review 2026-09-07): every StateDiff-typed field gets the diff's own
preparation and the diff's own field-level prune, not just `state_diff`.

`DirectorInterpret.state_assertions` is declared a `StateDiff` on purpose --
"interpret is not a lesser authority than resolve, it is the same authority
scoped to the player's input" -- and it received neither. The five recoveries
`preprocess_llm_output` runs for `director_resolve` (`_fill_entity_names`,
`_coerce_conditions`, `_coerce_optional_time`, `_hoist_misplaced_entity_
siblings`, `_coerce_empty_list_to_dict`) were keyed by the literal name
`state_diff`, and `_prunable_diff_fields` rooted on it alone. So a shape that
is silently recovered inside a resolve failed the whole interpret call and
bought a repair, and the player's asserted state went with it -- interpret's
whole point being that what the player says happens, happens THAT turn,
before perception fires.

The rule now: the roots are DERIVED from the step's model
(`state_diff_fields`), so a field added later is prepared and pruned without
anything being remembered.
"""

from __future__ import annotations

from llm.schemas import (SCHEMA_MAP, state_diff_fields,
                         validate_llm_output_strict as validate)

DECLARED = {"kind": "action", "sequence": [
    {"type": "action", "attempt": "shrug the coat off onto the chair"}]}


class TestTheRootsAreDerived:
    def test_interpret_declares_two_state_diff_roots(self, temp_db):
        assert state_diff_fields(SCHEMA_MAP["director_interpret"]) == {
            "state_assertions", "onset_state_assertions"}

    def test_resolve_declares_its_one(self, temp_db):
        assert state_diff_fields(SCHEMA_MAP["director_resolve"]) == {
            "state_diff"}


class TestInterpretGetsTheSameRecoveries:
    def test_an_entity_keyed_but_unnamed_is_recovered(self, temp_db):
        """`SceneEntityDef.name` is required and the key already carries it.
        Recovered inside `state_diff` since the split; inside
        `state_assertions` it failed the call."""
        report = validate("director_interpret", {
            **DECLARED,
            "state_assertions": {"entities": {
                "brass_key": {"kind": "object",
                              "description": "a small brass key"}}},
        }, source_payload={})
        assert report.valid, report.errors
        entities = report.output["state_assertions"]["entities"]
        assert entities["brass_key"]["name"] == "Brass Key"

    def test_a_scalar_time_is_coerced_rather_than_failing_the_call(
            self, temp_db):
        report = validate("director_interpret", {
            **DECLARED,
            "state_assertions": {"positions": {"Hinami": "hall"},
                                 "time": "about a minute"},
        }, source_payload={})
        assert report.valid, report.errors
        assert report.output["state_assertions"]["positions"] == {
            "Hinami": "hall"}

    def test_an_empty_list_for_a_keyed_table_is_coerced(self, temp_db):
        report = validate("director_interpret", {
            **DECLARED,
            "state_assertions": {"attire": [], "poses": []},
        }, source_payload={})
        assert report.valid, report.errors

    def test_a_sibling_written_inside_entities_is_hoisted_out(self, temp_db):
        """chat 80 turn 1's shape, on the interpret side: the model wrote the
        parent object's own sibling fields one nesting level too deep."""
        report = validate("director_interpret", {
            **DECLARED,
            "state_assertions": {"entities": {
                "brass_key": {"name": "brass key", "kind": "object"},
                "attire": {"Hinami": {"remove": ["coat"]}},
            }},
        }, source_payload={})
        assert report.valid, report.errors
        assertions = report.output["state_assertions"]
        assert set(assertions["entities"]) == {"brass_key"}
        assert assertions["attire"]["Hinami"]["remove"] == ["coat"]


class TestOneBadChannelCostsOnlyItself:
    def test_the_declaration_survives_a_malformed_assertion_channel(
            self, temp_db):
        report = validate("director_interpret", {
            **DECLARED,
            "state_assertions": {"positions": {"Hinami": "hall"},
                                 "conditions": "not a dict at all"},
        }, source_payload={})
        assert report.valid, report.errors
        assert report.output["sequence"][0]["attempt"] == (
            "shrug the coat off onto the chair")
        assert report.output["state_assertions"]["positions"] == {
            "Hinami": "hall"}
        assert not report.output["state_assertions"]["conditions"]
        assert any("state_assertions.conditions" in w
                   for w in report.warnings)

    def test_an_error_outside_the_roots_prunes_nothing(self, temp_db):
        """The sequence, the speech and the flow ARE interpret's
        adjudication -- the same rule the resolve prune states for prose."""
        report = validate("director_interpret", {
            "kind": "action",
            "sequence": "not a list at all",
            "state_assertions": {"conditions": "not a dict at all"},
        }, source_payload={})
        assert not report.valid
