"""Fill-in-the-blank psychology generation for older cards."""

import json
import time


def test_fill_psychology_preserves_authored_fields_and_fills_nested_gaps(
        temp_db, monkeypatch):
    from story import importers

    stored = {
        "identity": {"name": "Mara"},
        "psychology": {
            "drive": {
                "essence": "Protect the archive",
                "expression": "checks every seal herself",
                "taboo": "destroying evidence",
            },
            "traits": [{
                "name": "watchful", "strength": 0.8,
                "expression": "notices changed routines",
            }],
        },
    }
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(stored), "{}", time.time(), "char_mara"),
    )

    proposal = {
        "identity": {"name": "REPLACED"},
        "psychology": {
            "drive": {
                "essence": "REPLACE ME",
                "expression": "REPLACE ME",
                "taboo": "REPLACE ME",
            },
            "traits": [{
                "name": "watchful", "strength": 0.2,
                "expression": "REPLACE ME",
                "activation_cues": ["a broken routine"],
                "inhibited_by": ["trusted reassurance"],
            }],
            "self_model": {"beliefs": [{
                "belief": "If I miss one detail, people get hurt",
                "confidence": 0.8,
                "protected": True,
                "emotional_charge": -0.7,
                "source": "a past breach",
            }]},
        },
        "embodiment": {
            "visible": {"summary": "REPLACED APPEARANCE"},
            "interoception": {
                "acuity": 0.7, "pain_sensitivity": 0.4,
                "fatigue_sensitivity": 0.8, "pleasure_sensitivity": 0.3,
            },
        },
        "initial_state": {
            "goals": [{"goal": "REPLACED GOAL", "priority": 1.0}],
        },
    }
    monkeypatch.setattr(
        importers, "chat_complete",
        lambda *args, **kwargs: json.dumps(proposal),
    )

    sheet = importers.fill_character_psychology(
        char_id, "Hypervigilant after an archive breach.")

    assert sheet["psychology"]["drive"]["essence"] == "Protect the archive"
    trait = sheet["psychology"]["traits"][0]
    assert trait["strength"] == 0.8
    assert trait["expression"] == "notices changed routines"
    assert trait["activation_cues"] == ["a broken routine"]
    assert sheet["psychology"]["self_model"]["beliefs"][0]["protected"] is True
    assert sheet["embodiment"]["interoception"]["acuity"] == 0.7
    assert sheet["identity"]["name"] == "Mara"
    assert sheet["embodiment"]["visible"]["summary"] != "REPLACED APPEARANCE"
    assert sheet["initial_state"]["goals"] == []
    persisted = json.loads(temp_db.q(
        "SELECT sheet FROM characters WHERE id=?", (char_id,), one=True,
    )["sheet"])
    assert "self_model" not in persisted["psychology"]
    assert persisted["identity"]["name"] == "Mara"


def test_fill_prompt_is_specific_and_non_destructive():
    # The authored default, not `get_prompt` -- that resolves the active preset
    # and the NSFW flag from the settings table, and this is a fast-tier test
    # about what the prompt SAYS. Overriding the text in a preset is a separate
    # behaviour from having written it correctly.
    from llm.prompts import DEFAULT_PROMPTS

    prompt = DEFAULT_PROMPTS["fill_character_psychology"]
    assert "merges only empty fields" in prompt
    assert "formative pressures" in prompt
    assert "Do not diagnose" in prompt
