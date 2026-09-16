"""A spoken claim is evidence of speech, not an objective setting fact."""

from copy import deepcopy

import pytest

from agents import director
from world.causality import compile_transforms


def _cups_row():
    # Measured fresh novel-prose run: the author asserted Edda's speech,
    # while the Director incorrectly upgraded the quote into a train fact.
    return {
        "chrono_id": 10, "item_id": 1, "item_ids": [1, 2],
        "item_names": ["Edda", "Kian"], "object_name": "Edda",
        "source_entity_id": "persona:2", "authority_mode": "world_author",
        "source_event_id": "turn:2:primary:raw", "event": "No train until noon",
        "observable": "Edda speaks to Kian while facing the timetable",
        "commitment": "asserted", "targets": ["Kian"],
        "resolution_notes": "No train arrives before noon",
        "categories": ["speech", "world_facts"],
    }


def test_captured_cups_claim_does_not_become_a_world_fact():
    raw = {"chrono_id": 10, "item_id": 1, "patch": {
        "world_facts": ["No train arrives before noon"],
    }}
    original = deepcopy(raw)
    diff, history, rejected = compile_transforms(
        [raw], allowed_channels=["world_facts"], ledger_items=[_cups_row()],
        specialist="social")
    assert diff == {} and history == []
    assert rejected == [{
        "reason": "speech does not establish objective world_facts",
        "chrono_id": 10, "item_id": 1,
        "source_event_id": "turn:2:primary:raw",
        "channels": ["world_facts"],
        "value": ["No train arrives before noon"],
    }]
    assert raw == original


def test_world_fact_only_owner_does_not_receive_a_dialogue_transcript(monkeypatch):
    from agents.director import SPECIALISTS, reads_dialogue

    monkeypatch.setitem(SPECIALISTS, "social", {
        **SPECIALISTS["social"], "channels": ("world_facts",),
    })
    assert not reads_dialogue("social")


@pytest.mark.parametrize("marker", [
    {"type": "speech"}, {"type": "communication"},
    {"kind": "speech"}, {"categories": ["speech", "world_facts"]},
])
def test_typed_speech_boundary_is_language_independent_and_keeps_performatives(marker):
    row = {"chrono_id": 1, "item_id": 1, "event": "正午まで列車はない。", **marker}
    patch = {
        "world_facts": [{"fact": "No train before noon", "source": "mechanical"}],
        "public_evidence": [{"source_id": "quote:1", "speech_acts": [
            {"kind": "promise", "content": "I will wait."}]}],
        "charter_ops": [{"op": "order", "who": "Kian", "what": "wait"}],
        "speech": [{"speaker": "persona:2", "text": "I will wait."}],
    }
    diff, history, rejected = compile_transforms(
        [{"chrono_id": 1, "item_id": 1, "patch": patch}],
        allowed_channels=patch, ledger_items=[row], specialist="social")
    assert "world_facts" not in diff
    assert set(diff) == {"public_evidence", "charter_ops", "speech"}
    assert diff["speech"][0]["text"] == "I will wait."
    assert diff["public_evidence"][0]["source_id"] == "quote:1"
    assert diff["charter_ops"][0]["op"] == "order"
    assert set(history[0]["channels"]) == set(diff)
    assert len(rejected) == 1


@pytest.mark.parametrize("authority", ["world_author", "world", "mechanical"])
def test_independent_fact_on_same_object_has_its_own_chronology(authority):
    row = _cups_row()
    independent = {**row, "chrono_id": 11, "categories": ["world_facts"],
                   "source_entity_id": authority, "authority_mode": authority,
                   "event": "No train arrives before noon",
                   "source_event_id": "independent:1"}
    diff, history, rejected = compile_transforms([
        {"chrono_id": 10, "item_id": 1, "patch": {
            "world_facts": ["No train arrives before noon"]}},
        {"chrono_id": 11, "item_id": 1, "patch": {
            "world_facts": ["No train arrives before noon"]}},
    ], allowed_channels=["world_facts"], ledger_items=[row, independent])
    assert diff == {"world_facts": ["No train arrives before noon"]}
    assert [entry["chrono_id"] for entry in history] == [11]
    assert [entry["chrono_id"] for entry in rejected] == [10]


@pytest.mark.parametrize("ledger_items,transform", [
    (None, {"chrono_id": 1, "object_id": "legacy"}),
    ([_cups_row()], {"item_id": 1}),
    ([{"chrono_id": 1, "item_id": 1}], {"chrono_id": 1, "item_id": 1}),
])
def test_archived_facts_without_exact_typed_speech_provenance_remain_readable(
        ledger_items, transform):
    diff, history, rejected = compile_transforms([
        {**transform, "patch": {"world_facts": ["The line is closed."]}},
    ], allowed_channels=["world_facts"], ledger_items=ledger_items)
    assert not rejected
    assert diff == {"world_facts": ["The line is closed."]}
    assert len(history) == 1


def test_director_assembly_preserves_quote_and_evidence_but_rejects_its_claim(
        temp_db, monkeypatch):
    from tests.test_director_orchestration import _make_ctx, _fake_agent, _speech_interp

    interp = _speech_interp()
    interp["speech"] = interp["sequence"][0]["text"] = "No train until noon"
    row = {**_cups_row(), "chrono_id": 1, "item_ids": [1],
           "item_names": ["The Stranger"], "object_name": "The Stranger",
           "source_entity_id": "persona:primary", "targets": ["Mara"],
           "categories": ["speech", "world_facts", "public_evidence"]}
    evidence = {"source_id": "speech:The Stranger:0", "speech_acts": [
        {"kind": "disclosure", "content": "No train until noon"}]}
    responses = {
        "director_resolve": {"ledgers": [row]},
        "director_social": {"results": [{"status": "encoded", "transforms": [{
            "item": "The Stranger", "patch": {
                "world_facts": ["No train arrives before noon"],
                "public_evidence": [evidence],
            },
        }]}]},
    }
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], responses))
    ctx = _make_ctx(temp_db, interp=interp)
    out = director.director_resolve(ctx, nonce=0)
    assert not out["state_diff"].get("world_facts")
    history = out["orchestration"]["transform_history"]
    assert any(entry["patch"].get("public_evidence") for entry in history)
    assert not any(entry["patch"].get("world_facts") for entry in history)
    assert out["dialogue_log"][0]["exact_quote"].strip('"') == "No train until noon"
    assert any("speech does not establish objective world_facts" in warning
               for warning in ctx.warnings)
