"""Character-card editor coverage for v3 psychology."""

from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]


def test_character_editor_exposes_v3_psychology_and_hedonics():
    source = (ROOT / "static/js/ui-next/library-editors/character-persona.js").read_text(encoding="utf-8")
    sections = (ROOT / "static/js/ui-next/library-editors/person-sections.js").read_text(encoding="utf-8")
    runtime = (ROOT / "static/js/ui-next/library-authoring-runtime.js").read_text(encoding="utf-8")
    assert "Fill psychology" in source
    assert "createPersonSectionEditor" in source
    assert 'path: "psychology.stress_profile"' in sections
    assert 'path: "initial_state.hedonic"' in sections
    assert "createAdditionalNode" in sections
    assert "JSON.stringify(state.draft, null, 2)" in source
    assert "previewPsychology" in source
    assert "/fill_psychology" in runtime


def test_generation_and_import_prompts_emit_v3_fields():
    prompt_card = json.loads(
        (ROOT / "language_packs/en/cards/system_prompts.json").read_text(
            encoding="utf-8"))
    prompts = json.dumps(prompt_card)
    importers = (ROOT / "story" / "importers.py").read_text(encoding="utf-8")

    for token in (
        r"activation_cues",
        r"stress_profile",
        r"pleasure_sensitivity",
        r"associations",
    ):
        assert token in prompts
        assert token in prompt_card["prompts"]["import_character_reinterpret"]
    assert 'get_prompt("import_character_reinterpret")' in importers
