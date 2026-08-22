"""Validation for generated G1 browser and screenshot evidence."""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "design" / "sonder-ui-replacement" / "g1" / "foundation-report.json"


def test_foundation_report_covers_the_required_visual_matrix():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert len(report["source_commit"]) == 40
    assert len(report["source_tree_sha256"]) == 64
    assert report["browser"]
    cases = report["cases"]
    assert len({case["id"] for case in cases}) == len(cases)
    assert {case["theme"] for case in cases} == {
        "carbon-signal", "ash-brass", "midnight-ink", "parchment-night"
    }
    assert {case["viewport"]["width"] for case in cases} >= {360, 390, 844, 1024, 1440}
    preferences = {preference for case in cases for preference in case["preferences"]}
    assert preferences >= {
        "solid-surfaces", "reduced-motion", "accessibility-mode",
        "large-ui", "large-prose", "high-contrast", "long-copy",
    }


def test_every_foundation_capture_is_clean_and_present():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    for case in report["cases"]:
        assert case["console_errors"] == []
        assert case["page_errors"] == []
        assert case["api_requests"] == 0
        assert case["horizontal_overflow_px"] <= 1
        assert math.isfinite(case["minimum_target_px"])
        assert case["minimum_target_px"] >= 32
        screenshot = ROOT / case["screenshot"]
        assert screenshot.is_file()
        assert len(case["screenshot_sha256"]) == 64
        assert screenshot.stat().st_size > 1_000

