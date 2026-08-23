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
    sections = (
        RUNTIME / "library-editors" / "person-sections.js"
    ).read_text(encoding="utf-8")
    assert 'export const MODULE_RELEASE = "alpha98-ui4-842dd802b09f";' in editor
    assert "library-editors/character-persona.js" in bootstrap
    assert "createPersonEditor" in view
    for owned_path in (
        '"identity", "name"',
        '"identity", "aliases"',
        '"identity", "pronouns"',
        '"embodiment", "visible", "summary"',
        '"knowledge", "public_history"',
    ):
        assert owned_path in sections
    assert "JSON.stringify(state.draft, null, 2)" in editor
    assert "JSON.parse" in editor
    assert "services.authoring.stage(parsed, { render: true })" in editor
    assert "dataset.schemaPath" in sections
    assert "createPersonSectionEditor" in editor
    assert 'dotted === "identity.uid"' in sections
    assert "library-editors/person-sections.js" in bootstrap
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


def test_people_create_import_and_preview_tools_have_native_contracts():
    runtime = (RUNTIME / "library-authoring-runtime.js").read_text(encoding="utf-8")
    editor = (
        RUNTIME / "library-editors" / "character-persona.js"
    ).read_text(encoding="utf-8")
    detail = (RUNTIME / "library-view.js").read_text(encoding="utf-8")
    for path in (
        "/api/characters/new-document",
        "/api/personas/new-document",
        "/api/characters/generate-preview",
        "/api/personas/generate-preview",
        "/fill_psychology",
        "/fill_appearance",
        "/generate_greeting",
        "/recover_greetings_preview",
        "/api/characters/${active.id}/start",
        "/api/characters/import",
        "/api/personas/import",
    ):
        assert path in runtime
    for action in (
        "services.authoring.previewGenerate",
        "services.authoring.previewAppearance",
        "services.authoring.previewPsychology",
        "services.authoring.previewGreeting",
        "services.authoring.previewGreetingRecovery",
        "services.authoring.retryPreview",
        "services.authoring.discardPreview",
        "services.authoring.quickStart",
    ):
        assert action in editor
    assert "Create character" in detail
    assert "Create persona" in detail
    assert "Import character" in detail
    assert "Import persona" in detail


def test_people_editor_uses_bible_pane_and_cluster_contracts():
    editor = (
        RUNTIME / "library-editors" / "character-persona.js"
    ).read_text(encoding="utf-8")
    detail = (RUNTIME / "library-view.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "ui" / "library-authoring.css").read_text(
        encoding="utf-8"
    )
    assert "ui-authoring-form__header" in editor
    assert 'setAttribute("role", "toolbar")' in editor
    assert "ui-action-more__menu" in editor
    assert "ui-action-cluster" in detail
    assert ".ui-action-cluster" in css
    for responsive_contract in (
        ".ui-person-workspace",
        ".ui-person-editor__nav",
        ".ui-person-editor__panels",
        "overflow-y: auto",
        "min-block-size: 44px",
    ):
        assert responsive_contract in css
    for nonexistent_token in (
        "--ui-text-muted", "--ui-text-secondary", "--ui-surface-1",
        "--ui-border-subtle", "--ui-radius-2", "--ui-font-size-sm",
    ):
        assert nonexistent_token not in css


def test_story_card_override_is_a_native_owned_editor_route():
    runtime = (RUNTIME / "library-authoring-runtime.js").read_text(encoding="utf-8")
    editor = (
        RUNTIME / "library-editors" / "character-persona.js"
    ).read_text(encoding="utf-8")
    detail = (RUNTIME / "library-view.js").read_text(encoding="utf-8")
    assert "story-character:${storyId}:${id}" in runtime
    assert "/api/chats/${owner.storyId}/characters/${owner.id}/card" in runtime
    assert 'state.mode === "story-card"' in editor
    assert "Edit Story card" in detail
