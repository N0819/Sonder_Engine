"""Executable documentation for the current causal specialist contract.

Check the duplicated shared text for drift, then validate the English and
Japanese examples models may imitate against real schemas and item accounting.
These checks exercise examples, not live model reliability.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from agents import director
from llm import prompts
from llm.llm_quality import _step_json_schema
from llm.schemas import validate_llm_output_strict

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("en", "ja")
HANDS = ("body", "social", "contact", "objects", "spatial")
PRIVATE_FIELDS = {"chrono_id", "item_id", "item_ids"}

# Standing context from each example's premise, kept separate from its output
# so a syntactically valid patch on the wrong existing record still fails.
SCENARIOS = {
    "body": {
        "channels": ["attire"], "hands": ["body"], "bodies": ["Nia"],
        "entities": {"Orange jacket": {"name": "Orange jacket"}},
        "attire": {"Nia": {"wearing": ["Orange jacket"]}},
    },
    "social": {
        "channels": ["obligations"], "hands": ["social"],
        "bodies": ["Mira"], "entities": {},
    },
    "contact": {
        "channels": ["contact_ops"], "hands": ["contact"], "bodies": [],
        "entities": {"key_1": {"name": "Brass key"},
                     "door_1": {"name": "Storeroom door"}},
    },
    "objects": {
        "channels": ["inventory_ops"], "hands": ["objects", "contact"],
        "bodies": ["Sera", "Tomas"],
        "entities": {"tin_1": {"name": "Brass tin"}},
    },
    "spatial": {
        "channels": ["stations"], "hands": ["spatial"], "bodies": [],
        "entities": {"tin_1": {"name": "Brass tin"},
                     "worktop": {"name": "Worktop"}},
    },
}


def _example(language, hand):
    directory = (ROOT / "language_packs" / language / "cards"
                 / "system_prompts" / "specialists" / hand)
    text = (directory / "core.txt").read_text(encoding="utf-8")
    assert text.count("\nSHARED CONTRACT\n") == 1
    assert text.count("\nOUTPUT ENVELOPE") == 1
    shared = text.split("\nSHARED CONTRACT\n", 1)[1].split(
        "\nOUTPUT ENVELOPE", 1)[0]
    channel, = SCENARIOS[hand]["channels"]
    chunk = (directory / "chunks" / f"{channel}.txt").read_text(encoding="utf-8")
    assert chunk.count("\nWORKED EXAMPLE") == 1
    worked = chunk.split("\nWORKED EXAMPLE", 1)[1]
    # Both translations publish the literal item_names array in the premise.
    items = re.search(r"item_names[^\[\n]*(\[[^\]\n]*\])", worked)
    assert items is not None, f"{language}/{hand}: missing example input items"
    names = json.loads(items.group(1))
    lines = [line for line in worked.splitlines()
             if line.startswith('{"results":')]
    assert len(lines) == 1, f"{language}/{hand}: expected one complete example"
    return shared.strip(), names, json.loads(lines[0])


def _example_context(hand, names):
    scenario = deepcopy(SCENARIOS[hand])
    bodies = scenario["bodies"]
    scene = {
        "entities": scenario["entities"],
        "positions": {name: "workroom" for name in bodies},
        "attire": scenario.get("attire", {}),
        "rooms": {"workroom": {"name": "Workroom", "anchors": {
            "worktop": {"desc": "Worktop", "dir": "n"}}}},
    }
    ledger = {
        "chrono_id": 1, "item_ids": list(range(1, len(names) + 1)),
        "item_names": names, "categories": scenario["channels"],
        "assigned_hands": scenario["hands"],
    }
    public = director._specialist_ledger(ledger)
    matches = {}
    for label in names:
        candidates = [{"kind": "entity", "world_key": key, "name": record["name"]}
                      for key, record in scene["entities"].items()
                      if record["name"] == label]
        if label in bodies:
            candidates.append({"kind": "body", "world_key": label, "name": label})
        if candidates:
            matches[label] = candidates
    public["item_matches"] = matches
    payload = {
        "ledgers": [public], "completion_contract": "verified_effects_v1",
        "identity_index": {f"character:{i}": name for i, name in enumerate(bodies, 1)},
        "attire": scene["attire"],
        "worn_garments": [{"name": garment, "worn_by": wearer}
                          for wearer, attire in scene["attire"].items()
                          for garment in attire["wearing"]],
    }
    return ledger, payload, scene


def _all_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _all_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_keys(item)


def test_the_roster_this_file_pins_is_the_engines_roster():
    assert set(HANDS) == set(director.SPECIALISTS) == set(SCENARIOS)


def test_the_english_shared_contracts_agree_word_for_word():
    reference, _, _ = _example("en", "body")
    assert reference
    for hand in HANDS:
        shared, _, _ = _example("en", hand)
        assert shared == reference, f"en/{hand}: shared contract diverged"


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("hand", HANDS)
def test_channel_example_is_only_shown_when_its_channel_is_granted(language, hand, monkeypatch):
    _, _, example = _example(language, hand)
    granted = set(SCENARIOS[hand]["channels"])
    others = set(director.SPECIALISTS[hand]["channels"]) - granted
    # Exercise shipped prompt assembly, independent of host preset settings.
    monkeypatch.setattr(prompts, "_preset_override", lambda *_: None)
    for scope in (granted, others, set()):
        rendered = prompts.specialist_prompt(hand, scope, language)
        examples = [json.loads(line) for line in rendered.splitlines()
                    if line.startswith('{"results":')]
        assert examples.count(example) == int(granted <= scope), (
            f"{language}/{hand}: worked example escaped its channel grant")


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("hand", HANDS)
def test_worked_example_survives_current_scoped_validation(language, hand):
    _, names, example = _example(language, hand)
    _, payload, _ = _example_context(hand, names)
    step = f"director_{hand}"
    report = validate_llm_output_strict(step, deepcopy(example), source_payload=payload)
    assert report.valid, report.errors
    assert not report.warnings, report.warnings
    assert len(example["results"]) == len(payload["ledgers"])

    # Archive readers supply defaults; examples must contain current provider
    # generation requirements instead of passing through compatibility alone.
    schema = _step_json_schema(step)
    definitions = schema.get("$defs", schema.get("definitions"))
    result_schema = definitions["LedgerTransformResult"]
    transform_schema = definitions["LedgerPatchTransform"]
    assert set(schema["required"]) <= example.keys()
    granted = set(SCENARIOS[hand]["channels"])
    assert granted <= set(director.SPECIALISTS[hand]["channels"])
    possible_channels = {channel for spec in director.SPECIALISTS.values()
                         for channel in spec["channels"]}
    for result in example["results"]:
        assert set(result_schema["required"]) <= result.keys()
        assert result["status"] in result_schema["properties"]["status"]["enum"]
        assert set(result["settled"]) <= set(names)
        assert set(result["settled"].values()) <= {"not_mine", "no_referent"}
        assert set(result["required_channels"]) <= possible_channels
        assert result["reroute_to"] in {"", *HANDS}
        for transform in result["transforms"]:
            assert set(transform_schema["required"]) <= transform.keys()
            assert names.count(transform["item"]) == 1
            assert transform["patch"] and set(transform["patch"]) <= granted
    assert not PRIVATE_FIELDS & set(_all_keys(example))
    assert not PRIVATE_FIELDS & set(_all_keys(payload))


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("hand", ("body", "contact", "objects", "spatial"))
def test_physical_example_accounts_for_each_item_without_duplicate_relations(language, hand):
    _, names, example = _example(language, hand)
    ledger, _, scene = _example_context(hand, names)
    result = example["results"][0]
    covered, operations = set(), []
    for transform in result["transforms"]:
        item_id = names.index(transform["item"]) + 1
        touched = director._transform_covered_items(
            ledger, {**transform, "item_id": item_id}, scene)
        assert item_id in touched, "patch writes a different existing object"
        covered.update(touched)
        for channel in ("inventory_ops", "contact_ops"):
            operations.extend(json.dumps([channel, op], sort_keys=True)
                              for op in transform["patch"].get(channel, []))
    assert len(operations) == len(set(operations)), "relation duplicated per endpoint"
    uncovered = {name for item, name in zip(ledger["item_ids"], names)
                 if item not in covered}
    assert set(result["settled"]) == uncovered
    assert all(verdict == "not_mine" for verdict in result["settled"].values())
