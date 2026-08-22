"""Source contracts for lossless Character and Persona replacement editors."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "static" / "js" / "ui-next"


def test_people_editor_is_loaded_and_edits_complete_documents():
    bootstrap = (RUNTIME / "bootstrap.js").read_text(encoding="utf-8")
    view = (RUNTIME / "library-authoring-view.js").read_text(encoding="utf-8")
    editor = (
        RUNTIME / "library-editors" / "character-persona.js"
    ).read_text(encoding="utf-8")
    assert 'export const MODULE_RELEASE = "wp07.1";' in editor
    assert "library-editors/character-persona.js" in bootstrap
    assert "createPersonEditor" in view
    for owned_path in (
        '"identity", "name"',
        '"identity", "aliases"',
        '"identity", "pronouns"',
        '"embodiment", "visible", "summary"',
        '"knowledge", "public_history"',
    ):
        assert owned_path in editor
    assert "JSON.stringify(state.draft, null, 2)" in editor
    assert "JSON.parse" in editor
    assert "services.authoring.stage(parsed)" in editor
    for forbidden in (".innerHTML", "window.S", "MutationObserver", "clickLegacy"):
        assert forbidden not in editor


def test_people_actions_use_native_duplicate_export_and_revision_routes():
    runtime = (RUNTIME / "library-authoring-runtime.js").read_text(encoding="utf-8")
    detail = (RUNTIME / "library-view.js").read_text(encoding="utf-8")
    for path in (
        "/api/characters/${active.id}/duplicate",
        "/api/personas/${active.id}/duplicate",
    ):
        assert path in runtime
    assert "services.authoring.duplicate" in detail
    assert "/api/characters/${item.id}/export" in detail
    assert "/api/personas/${item.id}/export" in detail
