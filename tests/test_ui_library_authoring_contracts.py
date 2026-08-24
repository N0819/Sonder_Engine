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
        assert 'export const MODULE_RELEASE = "alpha98-ui8-eb87a8415bda";' in source
        assert name in bootstrap
    assert 'data-ui-next-version="alpha98-ui8-eb87a8415bda"' in html
    assert "/static/css/ui/library-authoring.css?release=alpha98-ui8-eb87a8415bda" in html


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
        '"/api/chats/import"',
        "/api/turns/${turnId}/branch",
        'channel: "library-authoring-import"',
        'channel: "library-authoring-branch"',
        "returnToLibrary",
        "delete query.mode",
        "delete query.session",
    ):
        assert required in source
    for forbidden in (
        "localStorage", "sessionStorage", "window.S", "MutationObserver",
        "setInterval(", "confirm(", "prompt(", ".innerHTML", "clickLegacy",
    ):
        assert forbidden not in source


def test_library_return_state_has_stable_scroll_and_focus_ownership():
    runtime = (RUNTIME / "library-runtime.js").read_text(encoding="utf-8")
    view = (RUNTIME / "library-view.js").read_text(encoding="utf-8")
    authoring_view = (RUNTIME / "library-authoring-view.js").read_text(
        encoding="utf-8"
    )
    assert "libraryScrollIdentity" in runtime
    assert "focusOnReturn" in runtime
    assert "returnFocusIdentity" in runtime
    assert "services.library.saveScroll(routeIdentity, scrollRegion.scrollTop)" in view
    assert "control.dataset.focusIdentity = `library-item:${item.key}`" in view
    assert "returnToLibrary(services" in authoring_view


def test_story_editor_uses_semantic_controls_and_never_parses_story_markup():
    source = (RUNTIME / "library-editors" / "story.js").read_text(encoding="utf-8")
    assert 'label.htmlFor' in source
    assert 'name = "name"' in source
    assert 'name = "scenario"' in source
    assert 'name = "persona_id"' in source
    assert "expected_revision" not in source
    for forbidden in (".innerHTML", "insertAdjacentHTML", "confirm(", "prompt("):
        assert forbidden not in source


def test_story_import_and_branch_are_routed_native_actions():
    editor = (RUNTIME / "library-editors" / "story.js").read_text(encoding="utf-8")
    view = (RUNTIME / "library-view.js").read_text(encoding="utf-8")
    inspector = (RUNTIME / "inspector-host.js").read_text(encoding="utf-8")
    assert 'name = "story_archive"' in editor
    assert "JSON.parse" in editor
    assert "services.authoring.importStory" in editor
    assert "services.authoring.retryImport" in editor
    assert "services.authoring.branchStory" in view
    assert '["edit", "import", "create", "story-card"].includes(route.query?.mode)' in inspector
    assert "Duplicate story" not in view


def test_library_home_surfaces_only_owned_recent_favorite_and_draft_keys():
    runtime = (RUNTIME / "library-runtime.js").read_text(encoding="utf-8")
    view = (RUNTIME / "library-view.js").read_text(encoding="utf-8")
    assert "homeState" in runtime
    assert 'drafts?.["library-authoring"]' in runtime
    for heading in ("Recent", "Favorites", "Drafts"):
        assert f'{heading.lower()}: "{heading}"' in view
    assert "draft.document" not in view
