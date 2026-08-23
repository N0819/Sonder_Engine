"""Exact-source closure contracts for the UI replacement release gate."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "docs/superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md"
TRACEABILITY = ROOT / "docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md"
CAPABILITIES = ROOT / "docs/design/sonder-ui-replacement/CAPABILITY_LEDGER.md"
WP07_REVIEW = ROOT / "docs/design/sonder-ui-replacement/WP07_REFERENCE_PORT_REVIEW.md"
WP14_REVIEW = ROOT / "docs/design/sonder-ui-replacement/wp14/REVIEW.md"
UNBUILT = ROOT / "docs/UNBUILT.md"


def test_release_traceability_has_no_open_requirement() -> None:
    source = TRACEABILITY.read_text(encoding="utf-8")
    assert "| open |" not in source
    assert source.count("| closed |") == 170
    assert "wp14/REVIEW.md" in source


def test_capability_ledger_names_only_current_replacement_owners() -> None:
    source = CAPABILITIES.read_text(encoding="utf-8")
    assert "not currently built" not in source
    assert "§2.26" not in source
    assert "static/js/ui-next/extensions.js" in source
    assert "browser_tests/test_ui_wp12.py" in source


def test_wp07_and_wp14_reviews_record_complete_gates() -> None:
    assert "**Status:** complete" in WP07_REVIEW.read_text(encoding="utf-8")
    review = WP14_REVIEW.read_text(encoding="utf-8")
    for required in (
        "Chromium",
        "Firefox",
        "WebKit",
        "Accessibility",
        "Performance",
        "Novice audit",
        "Expert audit",
        "No open P0 or P1",
    ):
        assert required in review


def test_completed_ui_replacement_is_not_left_in_unbuilt_register() -> None:
    source = UNBUILT.read_text(encoding="utf-8")
    assert "### 2.26 Replace the entire player and host web interface" not in source


def test_program_completion_checklist_is_closed() -> None:
    source = PROGRAM.read_text(encoding="utf-8")
    checklist = source.split("## Program completion checklist", 1)[1]
    checklist = checklist.split("Only then is the Sonder UI replacement finished.", 1)[0]
    assert "- [ ]" not in checklist
    assert checklist.count("- [x]") == 10
