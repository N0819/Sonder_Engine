"""Source boundaries for the replacement Library authoring substrate."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "static" / "js" / "ui-next"


def test_authoring_modules_are_release_coherent_and_loaded_explicitly():
    bootstrap = (RUNTIME / "bootstrap.js").read_text(encoding="utf-8")
    html = (ROOT / "static" / "ui-next.html").read_text(encoding="utf-8")
    for name in (
        "library-authoring-runtime.js",
        "library-authoring-view.js",
        "library-editors/story.js",
    ):
        source = (RUNTIME / name).read_text(encoding="utf-8")
        assert 'export const MODULE_RELEASE = "wp07.1";' in source
        assert name in bootstrap
    assert 'data-ui-next-version="wp07.1"' in html
    assert "/static/css/ui/library-authoring.css?release=wp07.1" in html


def test_authoring_runtime_owns_revisions_drafts_and_stale_responses():
    source = (RUNTIME / "library-authoring-runtime.js").read_text(encoding="utf-8")
    for required in (
        "/api/library/authoring/",
        "expected_revision",
        'channel: "library-authoring-load"',
        'channel: "library-authoring-save"',
        "isCurrent:",
        'setDraft("library-authoring"',
        'clearDraft("library-authoring"',
        'addEventListener("beforeunload"',
    ):
        assert required in source
    for forbidden in (
        "localStorage", "sessionStorage", "window.S", "MutationObserver",
        "setInterval(", "confirm(", "prompt(", ".innerHTML", "clickLegacy",
    ):
        assert forbidden not in source


def test_story_editor_uses_semantic_controls_and_never_parses_story_markup():
    source = (RUNTIME / "library-editors" / "story.js").read_text(encoding="utf-8")
    assert 'label.htmlFor' in source
    assert 'name = "name"' in source
    assert 'name = "scenario"' in source
    assert 'name = "persona_id"' in source
    assert "expected_revision" not in source
    for forbidden in (".innerHTML", "insertAdjacentHTML", "confirm(", "prompt("):
        assert forbidden not in source
