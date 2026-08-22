"""Validation and budget tests for the current-UI browser baseline.

These catch an incomplete or non-finite run being accepted as G0 evidence and
a release budget being set tighter than the measured current behavior without
an explicit rationale.
"""

from __future__ import annotations

import math

import pytest


def _valid_baseline() -> dict:
    return {
        "commit": "abc123",
        "browser": {"name": "chromium", "version": "1.2.3"},
        "platform": "test-platform",
        "journeys": {
            "play-empty": {"viewport": [1440, 900], "screenshot_sha256": "a" * 64},
            "play-populated": {"viewport": [1440, 900], "screenshot_sha256": "b" * 64},
            "library-scale": {"viewport": [1440, 900], "screenshot_sha256": "c" * 64},
            "settings": {"viewport": [1440, 900], "screenshot_sha256": "d" * 64},
            "new-story": {"viewport": [390, 844], "screenshot_sha256": "e" * 64},
            "login": {"viewport": [390, 844], "screenshot_sha256": "f" * 64},
            "guest-join": {"viewport": [390, 844], "screenshot_sha256": "0" * 64},
        },
        "metrics": {
            "boot_interactive_ms": {"median": 100.0, "p95": 125.0, "runs": 3},
            "transcript_500_render_ms": {"median": 300.0, "p95": 360.0, "runs": 3},
            "library_1000_render_ms": {"median": 400.0, "p95": 480.0, "runs": 3},
            "effects_frame_ms": {"median": 16.7, "p95": 22.0, "runs": 60},
            "navigation_dom_growth": {"median": 0.0, "p95": 3.0, "runs": 50},
            "idle_api_requests": {"median": 0.0, "p95": 0.0, "runs": 1},
        },
    }


def test_validation_rejects_missing_journeys_nonfinite_measures_and_idle_polling():
    from tools.capture_ui_baseline import validate_baseline

    missing = _valid_baseline()
    del missing["journeys"]["settings"]
    with pytest.raises(ValueError, match="settings"):
        validate_baseline(missing)

    nonfinite = _valid_baseline()
    nonfinite["metrics"]["boot_interactive_ms"]["p95"] = math.inf
    with pytest.raises(ValueError, match="finite"):
        validate_baseline(nonfinite)

    polling = _valid_baseline()
    polling["metrics"]["idle_api_requests"]["p95"] = 1.0
    with pytest.raises(ValueError, match="idle"):
        validate_baseline(polling)


def test_release_budgets_are_never_tighter_than_observed_baseline():
    from tools.capture_ui_baseline import derive_budgets

    baseline = _valid_baseline()
    budgets = derive_budgets(baseline)

    assert budgets["boot_interactive_p95_ms"] >= 125.0
    assert budgets["transcript_500_render_p95_ms"] >= 360.0
    assert budgets["library_1000_render_p95_ms"] >= 480.0
    assert budgets["effects_frame_p95_ms"] >= 22.0
    assert budgets["idle_api_requests"] == 0
    assert budgets["navigation_dom_growth_after_50"] >= 3.0

