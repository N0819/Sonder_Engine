"""Imported characters arrived without a drive, and sometimes hollow.

Reported live: importing character cards is unreliable at producing drives.
`psychology.drive` is Tier-1 of the goal hierarchy -- prompts.py derives
every proactive want from it, so a blank drive makes a character purely
reactive. Three separate causes:

A. `REINT_CHAR_SYS` (importers.py) never asked for one. The generator and
   promotion prompts in prompts.py were both given the "REQUIRED and
   load-bearing" drive paragraph and a template slot; the import path keeps
   its own copy of the schema prompt and was never updated.

B. The heuristic (LLM-free) path cannot author one by construction, and
   said nothing about it.

C. A model response missing one closing brace is repaired by `_jparse` into
   an object that parses but nests every remaining section under whichever
   one was left open. `_deep_defaults` keeps unknown keys verbatim and
   backfills the real slots with defaults, so the sheet the engine reads is
   hollow while the content sits inert one level down -- silently. Observed
   live on an imported character whose pronouns, aliases, voice, five
   abilities, whole history, three goals and first message were all parked
   under `psychology`.
"""

from __future__ import annotations

import json

from character_schema import (default_character_data, effective_drive,
                              normalize_character_data, repair_character_shape)
from importers import REINT_CHAR_SYS, character_import_warnings


# --- A: the prompt asks for it -------------------------------------------

def test_the_import_prompt_requires_a_drive_and_goals():
    assert '"drive":{"essence":"","expression":"","taboo":""}' in REINT_CHAR_SYS
    assert "DRIVE is the deepest thing this character lives for" in REINT_CHAR_SYS
    assert "STANDING GOALS" in REINT_CHAR_SYS


# --- B: a driveless import is announced ----------------------------------

def test_a_driveless_sheet_warns():
    warnings = character_import_warnings(default_character_data("Tamamo"))
    assert any("drive" in w for w in warnings)
    assert any("goals" in w for w in warnings)


def test_a_complete_sheet_warns_about_nothing():
    sheet = default_character_data("Tamamo")
    sheet["psychology"]["drive"] = {
        "essence": "Keep the seal intact", "expression": "Acts first",
        "taboo": "Will not abandon a post"}
    sheet["initial_state"]["goals"] = [{"goal": "Maintain the seal",
                                        "priority": 0.9}]
    assert character_import_warnings(sheet) == []


# --- C: the misnested sheet is repaired ----------------------------------

def _mangled():
    """The live shape: the skeleton at top level, the real content nested
    under `psychology` because a brace went missing after `coping`."""
    return {
        "identity": {"uid": "char_x", "name": "Tamamo", "aliases": [],
                     "pronouns": {"subject": "they", "object": "them",
                                  "possessive": "their"}},
        "name": "Tamamo",
        "aliases": ["Tamamo-no-Mae", "the Shrine Guardian"],
        "pronouns": {"subject": "she", "object": "her", "possessive": "her"},
        "competence": {"abilities": []},
        "initial_state": {"mood": {"label": "neutral", "valence": 0.0,
                                   "arousal": 0.0},
                          "goals": [], "active_concerns": []},
        "opening": {"first_message": ""},
        "psychology": {
            "traits": [{"name": "patient", "strength": 0.8, "expression": "waits"}],
            "coping": {"under_stress": [], "default_conflict_style": ""},
            "drive": {"essence": "Keep the seal intact",
                      "expression": "Acts before asked", "taboo": "Never abandons a post"},
            "competence": {"abilities": [
                {"name": "Rune crafting", "level": "master", "scope": "binding"}]},
            "initial_state": {"mood": {"label": "composed warmth",
                                       "valence": 0.3, "arousal": 0.1},
                              "goals": [{"goal": "Maintain the seal",
                                         "priority": 0.95}],
                              "active_concerns": []},
            "opening": {"first_message": "*A presence settles into the space.*"},
        },
    }


def test_misnested_sections_are_lifted_back_out():
    sheet = normalize_character_data(_mangled())

    assert [a["name"] for a in sheet["competence"]["abilities"]] == ["Rune crafting"]
    assert [g["goal"] for g in sheet["initial_state"]["goals"]] == ["Maintain the seal"]
    assert sheet["initial_state"]["mood"]["label"] == "composed warmth"
    assert sheet["opening"]["first_message"].startswith("*A presence")
    # The host section keeps only what belongs to it.
    assert "competence" not in sheet["psychology"]
    assert "opening" not in sheet["psychology"]
    # ...and its own content is untouched.
    assert effective_drive(sheet["psychology"], {})["essence"] == \
        "Keep the seal intact"


def test_a_flat_identity_is_folded_back_in():
    """Only `name` was ever rescued; pronouns and aliases were discarded, so
    an imported character silently became they/them with no aliases."""
    sheet = normalize_character_data(_mangled())
    assert sheet["identity"]["pronouns"]["subject"] == "she"
    assert sheet["identity"]["aliases"] == ["Tamamo-no-Mae", "the Shrine Guardian"]


def test_a_well_formed_sheet_is_left_alone():
    """The repair must not rearrange a sheet that was never broken."""
    good = default_character_data("Mara")
    good["psychology"]["drive"] = {"essence": "e", "expression": "x", "taboo": "t"}
    good["competence"]["abilities"] = [{"name": "Sailing", "level": "expert"}]
    assert repair_character_shape(good) == good


def test_the_richer_copy_wins_not_merely_the_outer_one():
    """The top-level copy is usually the skeleton the model emitted before it
    lost its place, so 'already present' must not mean 'authoritative'."""
    repaired = repair_character_shape(_mangled())
    assert repaired["competence"]["abilities"]          # nested content won
    # But a populated outer section is not replaced by a thinner nested one.
    other = {
        "competence": {"abilities": [{"name": "Real", "level": "master"}]},
        "psychology": {"competence": {"abilities": []}},
    }
    assert repair_character_shape(other)["competence"]["abilities"][0]["name"] \
        == "Real"


def test_legacy_sheets_normalize_with_a_drive_slot():
    legacy = {"name": "Old", "core": {"self_image": "a sailor"}}
    sheet = normalize_character_data(legacy)
    assert "drive" in sheet["psychology"]
    assert effective_drive(sheet["psychology"], {})["essence"] == ""


# ---------------------------------------------------------------------------
# The model does not get to name the engine's key for the character
# ---------------------------------------------------------------------------

def _card(name="Tamamo"):
    return {"spec": "chara_card_v2", "spec_version": "2.0",
            "data": {"name": name, "description": "An ancient kitsune.",
                     "personality": "", "scenario": "", "first_mes": ""}}


def test_a_reinterpreted_import_never_takes_the_models_uid(temp_db, monkeypatch):
    """identity.uid IS the scene entity id (scene.py falls back to it) and one
    of the forms character matching keys off. Live models return the
    character's own name for it -- GLM answers "tamamo" -- so two imports of
    one card became THE SAME ENTITY: two characters sharing one position, one
    set of clothes, one owner of the memories."""
    import importers

    sheet = {"identity": {"uid": "tamamo", "name": "Tamamo"},
             "psychology": {"drive": {"essence": "Guard the seal",
                                      "expression": "Stands watch", "taboo": "Never leaves"}},
             "initial_state": {"goals": [{"goal": "Hold the seal", "priority": 0.9}]}}
    monkeypatch.setattr(importers, "chat_complete",
                        lambda *a, **k: json.dumps(sheet))

    first = importers.import_character(_card(), reinterpret=True)[1]
    second = importers.import_character(_card(), reinterpret=True)[1]

    for got in (first, second):
        assert got["identity"]["uid"] != "tamamo"
        assert got["identity"]["uid"].startswith("char_")
    assert first["identity"]["uid"] != second["identity"]["uid"]


def test_a_native_reimport_still_round_trips_its_own_uid(temp_db):
    """The fix is scoped to sheets a model reconstructed. Re-importing this
    app's own export must keep the identity it exported, or every round trip
    would fork the character."""
    import importers
    from character_schema import default_character_data

    native = default_character_data("Tamamo")
    native["identity"]["uid"] = "char_deadbeefdeadbeefdeadbeefdeadbeef"
    _, sheet = importers.import_character({"sheet": native}, reinterpret=True)
    assert sheet["identity"]["uid"] == "char_deadbeefdeadbeefdeadbeefdeadbeef"
