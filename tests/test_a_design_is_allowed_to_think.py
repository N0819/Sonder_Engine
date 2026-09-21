"""The stream watchdog is tuned for a beat, and a location pass is not a beat.

`providers.PROVIDER_SILENCE_SECONDS` is 10, and its own note says what that
number is for: pipeline SPECIALISTS, "where the role's usual cost is 3-7 s",
tuned to catch two calls that took 1,324 s. For a stage a player is waiting on
that is right. For the most expensive call this engine makes it is not.

A location pass is 227-250 seconds over six to nine calls in which the Writers'
Room plans a whole inhabited place, and a reasoning model pauses for longer than
ten seconds inside one. Measured 2026-09-19/20: FOUR consecutive town designs
died on that watchdog, the last after 2,032 characters of reasoning and zero of
content -- a model that was working, killed for not having finished yet.

The fix is the one this file already uses for the socket deadline: the caller
that knows it is doing long work raises the limit for itself
(`providers.request_timeout` / `providers.patient_stream`), and every pipeline
stage keeps the threshold it was tuned for.
"""

from __future__ import annotations

import inspect

from llm import providers


class TestTheWatchdogTakesAnOverride:
    def test_the_default_is_the_tuned_pipeline_threshold(self):
        clock = providers._ActivityClock(
            limit=providers.silence_limit_override.get())
        assert clock.limit == providers.PROVIDER_SILENCE_SECONDS == 10.0

    def test_a_patient_caller_raises_it_for_itself(self):
        with providers.patient_stream(180):
            clock = providers._ActivityClock(
                limit=providers.silence_limit_override.get())
            assert clock.limit == 180.0

    def test_the_patience_does_not_leak_to_what_runs_next(self):
        """A contextvar left set would hand a player's beat the patience of a
        town design -- the same reason `request_timeout` resets in `finally`."""
        try:
            with providers.patient_stream(180):
                raise RuntimeError("the pass blew up")
        except RuntimeError:
            pass
        assert providers.silence_limit_override.get() is None

    def test_nothing_is_a_no_op_rather_than_an_error(self):
        for value in (0, None, "", "not a number"):
            with providers.patient_stream(value):
                assert providers.silence_limit_override.get() is None

    def test_the_stream_reads_the_override_rather_than_the_constant(self):
        """The wiring, not just the dial: a clock built from the constant
        would ignore every caller that asked for patience."""
        src = inspect.getsource(providers._sse_openai)
        assert "silence_limit_override.get()" in src


class TestTheLocationPassAsksForIt:
    def test_the_design_is_wrapped(self):
        from agents.story_planner import run_location_plan

        src = inspect.getsource(run_location_plan)
        assert "patient_stream(" in src
        assert "run_planner(" in src.split("patient_stream(")[1][:400], \
            "the planner call has to be INSIDE the patient block"

    def test_a_beat_is_not_wrapped(self):
        """Scoped deliberately. A pipeline stage that went quiet for three
        minutes would be a player staring at nothing, which is what the 10s
        threshold exists to prevent."""
        from agents import runtime

        assert "patient_stream" not in inspect.getsource(runtime)
