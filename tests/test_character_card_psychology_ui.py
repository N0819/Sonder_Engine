"""Character-card editor coverage for v3 psychology."""

from pathlib import Path
import json

from language_runtime import raw_card


ROOT = Path(__file__).resolve().parents[1]


def test_character_editor_exposes_v3_psychology_and_hedonics():
    source = (ROOT / "static/js/editors.js").read_text(encoding="utf-8")
    components = (ROOT / "static/js/components.js").read_text(encoding="utf-8")

    for token in (
        "Fill psychology gaps",
        "pain_sensitivity",
        "pleasure_sensitivity",
        "stress_profile",
        "coping_strategies",
        "associations",
        "initial_pleasure",
    ):
        assert token in source
    for helper in ("fBeliefs", "fCopingStrategies", "fAssociations"):
        assert f"function {helper}" in components


def test_generation_and_import_prompts_emit_v3_fields():
    prompt_card = raw_card("en")
    prompts = json.dumps(prompt_card, ensure_ascii=False)
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
