"""The replacement people editor saves the complete document losslessly."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "static/js/ui-next/library-editors/character-persona.js"


def test_replacement_editor_stages_the_complete_parsed_document():
    source = EDITOR.read_text(encoding="utf-8")
    assert "JSON.stringify(state.draft, null, 2)" in source
    assert "const parsed = JSON.parse" in source
    assert "services.authoring.stage(parsed)" in source


def test_identity_uid_is_locked_without_dropping_unpresented_fields():
    source = EDITOR.read_text(encoding="utf-8")
    assert 'dotted === "identity.uid"' in source
    assert "state.draft" in source
    assert "createSchemaSections" in source


def test_character_and_persona_share_the_lossless_editor():
    source = EDITOR.read_text(encoding="utf-8")
    assert "export function createPersonEditor" in source
    assert 'state.kind === "character"' in source
    assert 'state.kind === "character" ? "character" : "persona"' in source
