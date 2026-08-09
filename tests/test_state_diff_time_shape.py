"""One optional field killed a whole beat, and the example is why.

Live, 2026-08-08, GLM-5.2 on the director of a Green Door Inn scene:

    RuntimeError: director_resolve failed JSON validation:
    state_diff.time: value is not a valid dict

The model's response was otherwise correct — a full `resolved_event`, a
summary, the dialogue — and all of it was thrown away over one optional field.

THE CAUSE IS THE EXAMPLE, NOT THE MODEL. `prompts.py` describes the field in
prose ("Emit state_diff.time with start_seconds, duration_seconds,
end_seconds, mode ('action'|'time_skip'), explicit (bool), and
display_advance"), two thousand lines from the shape. `OUTPUT_EXAMPLES` — the
one concrete shape a model sees — showed `"time": null`. A model that copies
the example sends a scalar.

And the same example is the `required_json_example` handed to the repair
attempt, so the repair was shown the identical `null` and had no way to
converge. That is why a bounded repair loop did not save the turn.

Same class as the `ratified_claims` defect (described in prose, absent from
the shape the model fills), one step worse: described one way, SHOWN AS
ANOTHER TYPE.
"""

from __future__ import annotations

import pytest

from schemas import output_example, validate_llm_output_strict

# What the resolve prompt tells the model to emit, and therefore what the
# example has to show. Named here so a change to either has to change this
# list, rather than the two drifting silently apart again.
DOCUMENTED_TIME_FIELDS = ("start_seconds", "duration_seconds", "end_seconds",
                          "mode", "explicit", "display_advance")


def test_the_example_shows_the_shape_the_prompt_describes():
    """The defect itself. `null` is not a shape, and it is the only thing the
    model and the repair attempt are ever shown."""
    time = (output_example("director_resolve").get("state_diff") or {}).get("time")
    assert isinstance(time, dict), "the example must show an object, not null"
    for key in DOCUMENTED_TIME_FIELDS:
        assert key in time, f"the prompt asks for {key}; the example omits it"


def test_the_documented_shape_actually_validates(temp_db):
    """The example has to be an example of something the validator accepts —
    an example that would itself be rejected is worse than none."""
    example_time = output_example("director_resolve")["state_diff"]["time"]
    report = validate_llm_output_strict(
        "director_resolve",
        {"resolved_event": "x", "summary": "y",
         "state_diff": {"time": dict(example_time)}},
        source_payload={})
    assert report.valid, report.errors
    assert report.output["state_diff"]["time"] == example_time


@pytest.mark.parametrize("sent", [
    "a few minutes pass",     # the live shape: prose where an object belongs
    60,
    ["evening"],
    "",
])
def test_a_malformed_time_drops_instead_of_killing_the_beat(temp_db, sent):
    """Belt to the example's braces. `time` is Optional and the engine drifts
    its own clock without it, so an absent field is a state the engine already
    handles — while a dead turn loses the resolved_event, the dialogue and
    everything else in an otherwise correct response.

    Dropped, NOT invented: nothing truthful can be built from a bare string,
    and a fabricated duration would be a number the model never asserted.
    """
    report = validate_llm_output_strict(
        "director_resolve",
        {"resolved_event": "Hinami stows the broom.", "summary": "s",
         "state_diff": {"time": sent}},
        source_payload={})
    assert report.valid, report.errors
    # Absent, not null: the schema dump drops an unset Optional, and "absent"
    # is precisely the state commit.py already reads as "no advance asserted".
    assert report.output["state_diff"].get("time") is None
    # The rest of the response survives, which is the entire point.
    assert report.output["resolved_event"] == "Hinami stows the broom."


def test_a_real_time_object_is_untouched(temp_db):
    """The coercion must only ever DROP a malformed value. A dict passes
    through unchanged or this would quietly delete working time advances."""
    good = {"start_seconds": 0, "duration_seconds": 10800,
            "end_seconds": 10800, "mode": "time_skip",
            "explicit": True, "display_advance": "Hours pass"}
    report = validate_llm_output_strict(
        "director_resolve",
        {"resolved_event": "x", "summary": "y", "state_diff": {"time": good}},
        source_payload={})
    assert report.valid, report.errors
    assert report.output["state_diff"]["time"] == good
