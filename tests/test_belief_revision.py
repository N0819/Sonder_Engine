"""An explicit belief revision changes one held record without minting a rival."""

from copy import deepcopy

import pytest

from core.pipeline_context import current_warning_sink
from mind import psychology_runtime as psych


OLD = "The north stair is safe."
NEW = "The north stair cannot bear a person's weight."
EVIDENCE = {"event_id": "current:7:0", "fact": "The north stair collapsed."}


def _revision(target=OLD, belief=NEW, **fields):
    return {
        "operation": "revise", "target_belief": target, "belief": belief,
        "confidence": 0.95, "evidence": [dict(EVIDENCE)], **fields,
    }


def _apply(existing, updates, psychology=None, turn=7):
    return psych.apply_belief_updates(
        existing, psychology or {}, updates, turn_idx=turn,
        clock_seconds=turn * 10,
    )


def test_targeted_rewording_preserves_record_metadata_and_other_beliefs():
    existing = [
        {"belief": OLD, "confidence": 0.8, "id": "belief:stair",
         "source": "childhood", "emotional_charge": -0.2,
         "protected": False, "last_evidence": [{"event_id": "event:old"}]},
        {"belief": "The courtyard is quiet.", "confidence": 0.6,
         "source": "heard", "last_updated_turn": 2},
    ]
    original = deepcopy(existing)

    revised = _apply(existing, [_revision()])

    assert len(revised) == 2
    assert revised[0] == {
        **original[0], "belief": NEW, "confidence": 0.95,
        "last_updated_turn": 7, "last_updated_seconds": 70.0,
        "last_evidence": [EVIDENCE],
    }
    assert revised[1] == original[1]
    assert existing == original


@pytest.mark.parametrize("confidence,expected", [
    (0.0, 0.0), (0.6, 0.6), (1.5, 1.0), (-0.5, 0.0),
])
def test_targeted_same_text_sets_resulting_confidence(confidence, expected):
    revised = _apply(
        [{"belief": OLD, "confidence": 0.8, "protected": True}],
        [_revision(belief=OLD, confidence=confidence)],
    )

    assert len(revised) == 1
    assert revised[0]["belief"] == OLD
    assert revised[0]["confidence"] == expected
    assert revised[0]["protected"] is True


def test_target_matching_uses_exact_words_with_case_and_edge_whitespace_folded():
    revised = _apply(
        [{"belief": OLD, "confidence": 0.8}],
        [_revision(target=f"  {OLD.upper()}  ")],
    )

    assert [row["belief"] for row in revised] == [NEW]


@pytest.mark.parametrize("update,extra,warning", [
    (_revision(target="The northern stair is safe."), [], "unknown target"),
    (_revision(), [{"belief": NEW.upper(), "confidence": 0.3}],
     "already held by another belief"),
    (_revision(), [{"belief": OLD.upper(), "confidence": 0.3}],
     "ambiguous target"),
    (_revision(operation="reinforce"), [], "requires revise"),
    (_revision(operation="weaken"), [], "requires revise"),
])
def test_invalid_targeted_updates_warn_without_mutating_or_minting(
        update, extra, warning):
    existing = [
        {"belief": OLD, "confidence": 0.8, "last_updated_turn": 1},
        {"belief": "The courtyard is quiet.", "confidence": 0.6},
        *extra,
    ]
    original = deepcopy(existing)
    warnings = []
    token = current_warning_sink.set(warnings.append)
    try:
        revised = _apply(existing, [update])
    finally:
        current_warning_sink.reset(token)

    assert revised == original
    assert existing == original
    assert any(warning in message for message in warnings)


def test_two_targeted_revisions_in_one_batch_follow_current_wording():
    final = "Only the southern stair is usable."
    revised = _apply(
        [{"belief": OLD, "confidence": 0.8, "id": "belief:stair"}],
        [_revision(), _revision(target=NEW, belief=final, confidence=0.7)],
    )

    assert len(revised) == 1
    assert revised[0]["belief"] == final
    assert revised[0]["id"] == "belief:stair"
    assert revised[0]["confidence"] == 0.7


def test_authored_revision_keeps_origin_through_second_rename_and_ledger_cap():
    psychology = {"self_model": {"beliefs": [{
        "belief": OLD, "confidence": 0.9, "protected": True,
        "emotional_charge": 0.8, "source": "family teaching",
    }]}}
    seeded = _apply([], [], psychology)
    revised = _apply(seeded, [_revision()], psychology, turn=8)
    final = "The north stair is dangerous until repaired."
    revised = _apply(
        revised, [_revision(target=NEW, belief=final, confidence=0.85)],
        psychology, turn=9,
    )
    for turn in range(10, 10 + psych._LEDGER_CAP + 3):
        revised = _apply(revised, [{
            "belief": f"learned fact {turn}", "confidence": 0.7,
            "evidence": [dict(EVIDENCE)],
        }], psychology, turn=turn)
    revised = _apply(revised, [], psychology, turn=40)

    assert len(revised) == psych._LEDGER_CAP
    by_text = {row["belief"]: row for row in revised}
    assert OLD not in by_text
    assert NEW not in by_text
    assert by_text[final] == {
        **seeded[0], "belief": final, "authored_belief": OLD,
        "confidence": 0.85, "last_updated_turn": 9,
        "last_updated_seconds": 90.0, "last_evidence": [EVIDENCE],
    }

    # Explicit replacement does not remove the authored protection against
    # later ordinary weakening.
    weakened = _apply(revised, [{
        "belief": final, "operation": "weaken", "confidence": 1.0,
        "evidence": [dict(EVIDENCE)],
    }], psychology, turn=41)
    held = next(row for row in weakened if row["belief"] == final)
    assert held["confidence"] == pytest.approx(0.8)


def test_rewording_a_bare_protected_belief_does_not_reseed_its_old_text():
    psychology = {"self_model": {"protected_beliefs": [OLD]}}
    revised = _apply([], [_revision()], psychology)
    revised = _apply(revised, [], psychology, turn=8)

    assert len(revised) == 1
    assert revised[0]["belief"] == NEW
    assert revised[0]["authored_belief"] == OLD
    assert revised[0]["protected"] is True
    assert revised[0]["source"] == "protected_beliefs"


def test_targeted_revision_still_requires_evidence():
    existing = [{"belief": OLD, "confidence": 0.8, "protected": True}]

    assert _apply(existing, [_revision(evidence=[])]) == existing


def test_schema_and_grounding_preserve_target_and_zero_resulting_confidence():
    from agents.character import _ground_observation_citations
    from llm.schemas import BeliefUpdate

    existing = [{"belief": OLD, "confidence": 0.8}]
    output = {"belief_updates": [BeliefUpdate(
        **_revision(confidence=0.0),
    ).model_dump()]}
    _ground_observation_citations(output, [{
        "observation_id": EVIDENCE["event_id"],
        "observed": {"text": EVIDENCE["fact"]},
    }], {})
    revised = _apply(existing, output["belief_updates"])

    assert output["belief_updates"][0]["target_belief"] == OLD
    assert len(revised) == 1
    assert revised[0]["belief"] == NEW
    assert revised[0]["confidence"] == 0.0
    assert revised[0]["last_evidence"][0]["event_id"] == EVIDENCE["event_id"]


@pytest.mark.parametrize("evidence_ref", [
    "event:never-delivered", "summary:autobiographical:9",
])
def test_explicit_target_cannot_bypass_learning_evidence_grounding(evidence_ref):
    from agents.character import _ground_observation_citations

    existing = [{"belief": OLD, "confidence": 0.8}]
    output = {"belief_updates": [_revision(evidence=[{
        "event_id": evidence_ref,
    }])]}
    warnings = _ground_observation_citations(output, [], {
        "summary_citations": {"autobiographical_summary": {
            "summary_id": "summary:autobiographical:9",
        }},
    })

    assert output["belief_updates"] == []
    assert _apply(existing, output["belief_updates"]) == existing
    assert any("unsupported" in warning for warning in warnings)


def test_legacy_untargeted_revise_keeps_existing_weakening_and_mint_behavior():
    existing = [{"belief": OLD, "confidence": 0.8, "protected": True}]
    revised = _apply(existing, [_revision(target="", belief=OLD)])
    assert revised[0]["confidence"] == pytest.approx(0.8 - 0.05 * 0.95)
    assert "authored_belief" not in revised[0]

    minted = _apply(existing, [_revision(target="")])
    assert minted[0] == existing[0]
    assert minted[1]["belief"] == NEW
    assert minted[1]["confidence"] == 0.95


def test_targeted_revision_keeps_only_latest_three_evidence_records():
    evidence = [{"event_id": f"event:{n}"} for n in range(5)]
    revised = _apply(
        [{"belief": OLD, "confidence": 0.8}],
        [_revision(evidence=evidence)],
    )

    assert revised[0]["last_evidence"] == evidence[-3:]
