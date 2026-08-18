"""An entity def may omit `name`; the dict key already carries it.

Reported from live play (chat "The Doctor — Hinami ⎇14 ⎇17 ⎇16 ⎇23", glm-latest
as Director):

    Pipeline error: director_resolve failed JSON validation:
    state_diff.entities.sake_carafe.name: field required;
    state_diff.entities.computer.name: field required

`entities` is `dict[str, SceneEntityDef]`, so the key IS the identifier and a
model reasonably omits the redundant `name`. Failing the entire turn over a
field recoverable from its own key is the same over-strictness the dialogue_log
repair already addresses -- and the derivation is not guesswork: the same chat's
SUCCESSFUL turns show the model applying exactly this transformation itself
("guinan_entity" -> "Guinan", "turbolift_car_entity" -> "Turbolift Car").
"""

from __future__ import annotations

import pytest

from schemas import _entity_name_from_key, validate_llm_output_strict


@pytest.mark.parametrize("key,expected", [
    ("sake_carafe", "Sake Carafe"),
    ("computer", "Computer"),
    # Suffixes the model adds only to keep the id distinct are not part of the
    # display name -- confirmed against its own successful outputs.
    ("guinan_entity", "Guinan"),
    ("turbolift_car_entity", "Turbolift Car"),
    ("ready-room", "Ready Room"),
    # Deliberate acronyms must survive title-casing.
    ("LCARS_panel", "LCARS Panel"),
])
def test_name_derived_from_key(key, expected):
    assert _entity_name_from_key(key) == expected


def test_the_reported_failure_now_validates():
    """The exact payload shape from the live report."""
    raw = {
        "resolved_event": "Beverly sets the carafe down.",
        "state_diff": {"entities": {
            "sake_carafe": {"kind": "object", "description": "A warm carafe.",
                            "portable": True},
            "computer": {"kind": "object", "description": "LCARS terminal."},
        }},
    }
    report = validate_llm_output_strict("director_resolve", raw)
    assert report.valid, report.errors
    entities = report.output["state_diff"]["entities"]
    assert entities["sake_carafe"]["name"] == "Sake Carafe"
    assert entities["computer"]["name"] == "Computer"


def test_an_explicit_name_always_wins():
    raw = {"state_diff": {"entities": {
        "sake_carafe": {"name": "Captain's Sake", "kind": "object"}}}}
    report = validate_llm_output_strict("director_resolve", raw)
    assert report.output["state_diff"]["entities"]["sake_carafe"]["name"] \
        == "Captain's Sake"


@pytest.mark.parametrize("alias", ["label", "title", "display_name"])
def test_common_name_aliases_are_accepted(alias):
    """Mirrors the dialogue_log alias handling: a model reaching for a
    near-synonym should not fail the turn."""
    raw = {"resolved_event": "Beverly sets it down.",
           "state_diff": {"entities": {"sake_carafe": {alias: "Sake Carafe",
                                                       "kind": "object"}}}}
    report = validate_llm_output_strict("director_resolve", raw)
    assert report.valid, report.errors
    assert report.output["state_diff"]["entities"]["sake_carafe"]["name"] \
        == "Sake Carafe"


def test_blank_name_is_replaced_not_kept():
    """An empty string satisfies `name: str` but leaves the entity invisible to
    every display-name reader (commit.track_background_presences,
    agents/background._name_to_entity_id)."""
    raw = {"state_diff": {"entities": {"sake_carafe": {"name": "   ",
                                                       "kind": "object"}}}}
    report = validate_llm_output_strict("director_resolve", raw)
    assert report.output["state_diff"]["entities"]["sake_carafe"]["name"] \
        == "Sake Carafe"


def test_opening_turn_entities_are_covered_too():
    """director_establish carries entities at top level, not in a state_diff."""
    raw = {"location": "Ten Forward", "time": "night",
           "scene_description": "A quiet lounge.",
           "rooms": {"ten_forward": {"name": "Ten Forward", "desc": "Lounge."}},
           "positions": {"Beverly Crusher": "ten_forward"},
           "entities": {"sake_carafe": {"kind": "object"}}}
    report = validate_llm_output_strict("director_establish", raw)
    assert report.valid, report.errors
    assert report.output["entities"]["sake_carafe"]["name"] == "Sake Carafe"


def test_mapping_scene_patch_entities_are_named():
    """ScenePatch.entities is untyped so this never failed validation -- but a
    nameless entity still reaches the scene, where readers key display name to
    entity id."""
    raw = {"scene_patch": {"entities": {"sake_carafe": {"kind": "object"}}}}
    report = validate_llm_output_strict("mapping_stage", raw)
    assert report.output["scene_patch"]["entities"]["sake_carafe"]["name"] \
        == "Sake Carafe"


def test_a_scalar_entity_value_keeps_the_entity():
    """Malformed input must not raise inside preprocessing.

    That is what this test was written for and it is unchanged. The
    CONSEQUENCE has moved twice, each time toward keeping more:

    * Originally the whole resolve was rejected.
    * 2026-08-08: the malformed sub-field was pruned and the beat committed
      what it did adjudicate. The docstring at the time recorded the cost --
      "`entities` is the most consequential field to drop, a minted carafe is
      genuinely lost" -- and accepted it, because losing the entity beats
      losing the beat.
    * Now the carafe survives. A bare scalar where an object was declared is
      read as that object's SUBJECT, and `SceneEntityDef`'s subject is `name`,
      so `{"sake_carafe": "a carafe"}` is a complete answer to what the entity
      IS written in the shorter spelling. Nothing is dropped and nothing is
      guessed: an item model with no answerable subject slot still fails.

    Found through `poses`, where the same shortcut killed the opening turn of
    a story -- six bodies answering `"standing"` instead of
    `{"posture": "standing"}`.
    """
    raw = {"state_diff": {"entities": {"sake_carafe": "a carafe"}}}
    report = validate_llm_output_strict("director_resolve", raw)
    assert report.valid
    entity = report.output["state_diff"]["entities"]["sake_carafe"]
    assert entity["name"] == "a carafe"
    # The rest of the entity is its declared defaults, not invention.
    assert entity["description"] == ""
    assert entity["portable"] is False
