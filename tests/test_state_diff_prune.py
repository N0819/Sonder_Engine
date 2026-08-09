"""One bad field stops costing the whole beat.

Live 2026-08-08: a complete, correct 4,000-token resolve — `resolved_event`,
summary and dialogue all intact — was discarded because `state_diff.time`
arrived as a scalar. The repair attempt was then handed the same broken
example that caused it (`OUTPUT_EXAMPLES` showed `"time": null`) and could not
converge, so a bounded repair loop did not save it either.

`_coerce_optional_time` fixed that one field. This is the general form, and the
same shape as the lorebook import's repair-then-degrade (dce2b86): when EVERY
error is rooted under a `state_diff` sub-field, drop those sub-fields and
re-validate.

Why that is safe and the alternative is not: `state_diff` is an ENCODING of an
adjudication, not the adjudication. Absent is already "no change asserted" for
every StateDiff field, the reconcile seam (`resolve_reconcile`/`resolve_repair`)
exists precisely to catch changes asserted in prose but missing from the diff,
and commit stays atomic. The prose, the dialogue and the summary ARE the
adjudication — a beat without them is not a beat, so an error touching any of
them prunes nothing.
"""

from __future__ import annotations

import pytest

from schemas import validate_llm_output_strict as validate

GOOD_PROSE = {"resolved_event": "Hinami stows the broom.", "summary": "s"}


class TestTheBeatSurvivesAMalformedDiff:
    def test_the_prose_and_the_good_half_of_the_diff_survive(self, temp_db):
        report = validate("director_resolve",
                          {**GOOD_PROSE,
                           "state_diff": {"positions": {"Hinami": "hall"},
                                          "conditions": "not a dict at all"}},
                          source_payload={})
        assert report.valid, report.errors
        assert report.output["resolved_event"] == "Hinami stows the broom."
        assert report.output["state_diff"]["positions"] == {"Hinami": "hall"}
        # Back as its schema default rather than absent, which is the same
        # statement: an empty `conditions` asserts no condition change, and
        # that is precisely what a dropped malformed one should say.
        assert not report.output["state_diff"]["conditions"]

    def test_the_drop_is_reported_not_silent(self, temp_db):
        """A beat that quietly loses a state change is worse than one that
        says so: the warning is what makes the drift findable later."""
        report = validate("director_resolve",
                          {**GOOD_PROSE, "state_diff": {"conditions": "bad"}},
                          source_payload={})
        assert report.valid
        assert any("conditions" in w for w in report.warnings)

    @pytest.mark.parametrize("field,value", [
        ("time", "a few minutes pass"),
        ("conditions", "not a dict"),
        ("positions", 12),
        ("entities", "nope"),
    ])
    def test_it_generalises_past_the_one_field_that_was_patched(
            self, temp_db, field, value):
        report = validate("director_resolve",
                          {**GOOD_PROSE, "state_diff": {field: value}},
                          source_payload={})
        assert report.valid, report.errors
        assert report.output["resolved_event"]


class TestWhatMustStillFail:
    def test_an_error_in_the_adjudication_prunes_nothing(self, temp_db):
        """`dialogue_log` is the beat, not an encoding of it. Even beside a
        prunable diff error, it must still fail — pruning here would commit a
        beat whose dialogue the engine could not read."""
        report = validate("director_resolve",
                          {**GOOD_PROSE, "dialogue_log": "not a list",
                           "state_diff": {"conditions": "bad"}},
                          source_payload={})
        assert not report.valid
        assert any("dialogue_log" in e for e in report.errors)

    def test_a_prose_error_alone_still_fails(self, temp_db):
        report = validate("director_resolve",
                          {**GOOD_PROSE, "dialogue_log": "not a list",
                           "state_diff": {}},
                          source_payload={})
        assert not report.valid

    def test_a_valid_diff_is_never_touched(self, temp_db):
        """The pruning path must be unreachable for output that validates, or
        it would quietly delete working state changes."""
        diff = {"positions": {"Hinami": "hall"},
                "time": {"start_seconds": 0, "duration_seconds": 60,
                         "end_seconds": 60, "mode": "action",
                         "explicit": False, "display_advance": ""}}
        report = validate("director_resolve",
                          {**GOOD_PROSE, "state_diff": dict(diff)},
                          source_payload={})
        assert report.valid, report.errors
        assert report.output["state_diff"]["positions"] == diff["positions"]
        assert report.warnings == []

    def test_other_steps_are_unaffected(self, temp_db):
        """Only the resolve steps encode an adjudication this way. A mapping
        or perception step losing a field silently would be a real loss."""
        from schemas import _DIFF_PRUNABLE_STEPS
        assert set(_DIFF_PRUNABLE_STEPS) == {"director_resolve", "resolve_repair"}
