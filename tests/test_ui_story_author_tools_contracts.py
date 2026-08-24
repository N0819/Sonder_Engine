"""Source contracts for WP-05 long-form story author controls."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "static" / "js" / "ui-next" / "story-tools"
MODULES = ("document-editor.js", "world.js", "style.js", "dialogue.js", "attire.js")


def test_story_author_controls_are_native_release_coherent_modules():
    assert [name for name in MODULES if not (TOOLS / name).is_file()] == []
    for name in MODULES:
        assert 'export const MODULE_RELEASE = "alpha98-ui6-ff8a9b712a2d";' in (TOOLS / name).read_text(
            encoding="utf-8"
        )
    family = (TOOLS.parent / "live-story-tools.js").read_text(encoding="utf-8")
    for name in MODULES[1:]:
        assert f'./story-tools/{name}?release=alpha98-ui6-ff8a9b712a2d' in family


def test_world_and_attire_preserve_complete_authoritative_payloads():
    world = (TOOLS / "world.js").read_text(encoding="utf-8")
    attire = (TOOLS / "attire.js").read_text(encoding="utf-8")
    assert "/api/chats/${chatId}/world" in world
    assert "rooms" in world and "entities" in world and "positions" in world
    assert "/api/chats/${chatId}/attire" in attire
    assert "wearing" in attire and "regions" in attire
    for source in (world, attire):
        assert "mountDocumentEditor" in source
        assert '"PUT"' in source


def test_style_preserves_story_language_survival_and_authority_without_ui_language():
    source = (TOOLS / "style.js").read_text(encoding="utf-8")
    for route in (
        "/style_guide",
        "/language",
        "/survival",
        "/player_authority",
    ):
        assert route in source
    for field in (
        "genre",
        "tone",
        "director_notes",
        "mapping_notes",
        "avoid",
        "weather_severity",
    ):
        assert field in source
    assert "/api/ui-language" not in source
    assert "ui_language" not in source


def test_dialogue_preserves_all_three_server_documents_and_validates_numbers():
    source = (TOOLS / "dialogue.js").read_text(encoding="utf-8")
    for route in ("/dialogue_config", "/background_config", "/living_world"):
        assert route in source
    for field in (
        "initial_parallel_reactors",
        "parallel_isolated_reactors",
        "promote_after_addressed",
        "offscreen_life",
        "max_offscreen_actors",
        "max_managed",
        "max_reactors",
    ):
        assert field in source
    assert "validateDialogueDocument" in source
    assert 'setCustomValidity' in source


def test_long_form_tools_keep_owner_scoped_drafts_until_accepted_or_discarded():
    source = (TOOLS / "document-editor.js").read_text(encoding="utf-8")
    for contract in (
        "localState.getDraft",
        "localState.setDraft",
        "localState.clearDraft",
        "owner",
        "Discard draft",
        "Save changes",
        "Invalid JSON",
    ):
        assert contract in source
    assert "setInterval(" not in source
    assert ".innerHTML" not in source
    assert "prompt(" not in source
    assert "confirm(" not in source
