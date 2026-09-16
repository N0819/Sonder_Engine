"""Decisions and their reasons survive deterministic affect normalization."""

from copy import deepcopy

import pytest

from mind.affect import (
    appraise,
    apply_intent_ops,
    normalize_wants,
    resolve_affect,
    settle_intent_world_anchors,
)


def _want(text, urgency, serves="drive", **extra):
    return {"want": text, "urgency": urgency, "serves": serves, **extra}


def test_lower_urgency_restraint_survives_kernel_compilation_and_normalization():
    from agents.character_kernel import compile_character_kernel

    raw = {
        "state": {
            "active": {"wants": [
                {"id": "w1", **_want("Protect my friend from the storm", 0.4)},
                {"id": "w2", **_want("Run alone toward the safe tower", 0.9,
                                     conflicts_with="w1")},
            ]},
            "decision": {"enact": "w1", "suppress": "w2",
                         "hinge": "I promised not to abandon her"},
        },
        "sequence": [{"type": "action", "attempt": "stay beside my friend",
                      "observable": "stays beside her"}],
    }
    compiled, _ = compile_character_kernel(raw)
    state = compiled["active_state"]
    wants, enacted, suppressed = normalize_wants(
        state["wants"], set(), enacted_want=state["enacted_want"],
        suppressed_want=state["suppressed_want"])

    assert enacted == 0 and suppressed == 1
    assert wants[enacted]["want"] == "Protect my friend from the storm"
    assert wants[enacted]["enacted"] is True
    assert wants[suppressed]["suppressed"] is True


def test_choices_are_remapped_after_junk_deduplication_and_capacity():
    raw = [None, _want("guard the door", 0.95), _want("polish the armor", 0.8),
           _want("guard the door", 0.2), _want("write a letter", 0.1),
           _want("practice swordplay", 0.9)]
    before = deepcopy(raw)
    wants, enacted, suppressed = normalize_wants(
        raw, set(), want_cap=2, enacted_want=3, suppressed_want=4)

    assert [w["want"] for w in wants] == ["guard the door", "write a letter"]
    assert wants[0]["urgency"] == 0.2  # retain the actual chosen formulation
    assert (enacted, suppressed) == (0, 1)
    assert raw == before


@pytest.mark.parametrize("choice", ["enacted_want", "suppressed_want"])
def test_selected_situational_desire_gets_the_single_situational_slot(choice):
    raw = [_want("guard the door", 0.9),
           _want("drink some wine", 0.8, "situational"),
           _want("write a letter", 0.2, "unknown-intent")]
    wants, enacted, suppressed = normalize_wants(raw, set(), **{choice: 2})

    assert [w["want"] for w in wants] == ["guard the door", "write a letter"]
    assert wants[1]["serves"] == "situational"
    assert enacted == (1 if choice == "enacted_want" else 0)
    assert suppressed == (1 if choice == "suppressed_want" else None)


@pytest.mark.parametrize("same_desire,cap,situational", [
    (True, 3, False), (False, 1, False), (False, 3, True),
])
def test_enacted_choice_wins_when_suppression_cannot_fit(same_desire, cap, situational):
    serves = "situational" if situational else "drive"
    wants, enacted, suppressed = normalize_wants([
        _want("guard the door", 0.2, serves),
        _want("guard the door" if same_desire else "write a letter", 0.9, serves),
        _want("polish the armor", 0.8, conflicts_with="guard the door"),
    ], set(), want_cap=cap, enacted_want=0, suppressed_want=1)

    assert wants[enacted]["want"] == "guard the door"
    assert suppressed is None  # never invent a replacement for a lost choice
    assert not any(w.get("suppressed") for w in wants)
    assert sum(w["serves"] == "situational" for w in wants) <= 1


@pytest.mark.parametrize("invalid", [None, -1, 99, True, "1", 1.0, 2, 3])
def test_invalid_or_absent_indexes_keep_legacy_urgency_selection(invalid):
    raw = [_want("guard the door", 0.9),
           _want("write a letter", 0.7, conflicts_with="guard the door"),
           None, {}]
    expected = normalize_wants(raw, set())
    assert expected[1:] == (0, 1)
    assert normalize_wants(raw, set(), enacted_want=invalid,
                           suppressed_want=invalid) == expected


def _intent(**extra):
    return {"id": "i1", "intent": "Reach the healer before nightfall",
            "status": "active", "formed_turn": 1, "last_progress_turn": 1,
            "progress": 0.4, **extra}


@pytest.mark.parametrize("op", ["add", "progress", "block", "satisfy", "abandon", "nonviable"])
def test_each_accepted_intention_change_carries_one_reason_and_evidence(op):
    source = [] if op == "add" else [_intent()]
    evidence = [{"event_id": "event:bridge", "fact": "The bridge collapsed."}]
    result, warnings = apply_intent_ops(source, [{
        "op": op, "id": "i1", "intent": "Reach the healer before nightfall",
        "why": "The bridge collapsed; seek the lower crossing.", "evidence": evidence,
    }], 2, lambda _op: True)

    assert warnings == []
    assert result[0]["last_transition"] == {
        "op": op, "turn": 2,
        "why": "The bridge collapsed; seek the lower crossing.",
        "evidence": evidence,
    }
    if source:
        assert "last_transition" not in source[0]


def test_last_reason_replaces_prior_reason_and_is_bounded_without_copying_extra_fields():
    initial, _ = apply_intent_ops([], [{"op": "add", "intent": "Find the healer",
                                       "why": "Someone needs help."}], 1, lambda _op: True)
    evidence = [{"event_id": f"memory:{i}", "fact": "f" * 500,
                 "irrelevant": {"transcript": "do not copy"}} for i in range(6)]
    before = deepcopy(initial)
    result, _ = apply_intent_ops(initial, [{"op": "progress", "id": "i1",
                                          "why": "w" * 500, "evidence": evidence}],
                                 2, lambda _op: True)
    transition = result[0]["last_transition"]

    assert transition["op"] == "progress" and transition["turn"] == 2
    assert len(transition["why"]) == 240
    assert len(transition["evidence"]) == 3
    assert all(set(ref) == {"event_id", "fact"} and len(ref["fact"]) == 240
               for ref in transition["evidence"])
    assert initial == before
    assert len(evidence) == 6


@pytest.mark.parametrize("op,extra,barren", [
    ("satisfy", {}, False), ("abandon", {}, False), ("nonviable", {}, False),
    ("progress", {"progress": 1.0}, False), ("progress", {}, True),
    ("add", {"progress": 1.0}, False), ("add", {}, True),
    ("unknown", {}, False),
])
def test_rejected_or_barren_ops_do_not_replace_last_reason(op, extra, barren):
    transition = {"op": "add", "turn": 1, "why": "My friend needs help.", "evidence": []}
    source = [_intent(last_transition=transition, **extra)]
    before = deepcopy(source)
    result, warnings = apply_intent_ops(source, [{
        "op": op, "id": "i1", "intent": source[0]["intent"],
        "why": "This unaccepted reason must not replace the old one.",
    }], 2, lambda _op: False, barren_beat=barren)

    assert warnings
    assert result[0]["last_transition"] == transition
    assert source == before


def test_duplicate_add_records_progress_and_survives_next_turn_read_normalizers():
    from agents.character import _annotate_fading, _merge_standing_intentions

    source = [_intent(status="blocked", blocked_why="Bridge gone", blocked_turn=1)]
    result, warnings = apply_intent_ops(source, [{
        "op": "add", "intent": source[0]["intent"],
        "why": "The ferryman agreed to take me across.",
        "evidence": [{"event_id": "memory:crossing"}],
    }], 2, lambda _op: True)
    assert warnings == []
    assert len(result) == 1 and result[0]["status"] == "active"
    assert "blocked_why" not in result[0]
    expected = deepcopy(result[0]["last_transition"])
    assert expected["op"] == "progress"

    next_turn, _ = apply_intent_ops(result, [], 3, lambda _op: True)
    next_turn, _ = settle_intent_world_anchors(next_turn, [], 3, lambda *_args: False)
    payload = _annotate_fading(_merge_standing_intentions([_intent()], next_turn), 3)
    assert len(payload) == 1
    assert payload[0]["last_transition"] == expected


_PREV = {
    "surface": {"label": "anxious", "valence": -0.4, "arousal": 0.3},
    "undercurrent": {"label": "fear", "valence": -0.5, "arousal": 0.4,
                     "source": "the guard suspects her", "serves": "i1"},
    "baseline": {"valence": 0.0, "arousal": 0.0},
}


def test_explicit_null_clears_undercurrent_while_omission_only_decays():
    before = deepcopy(_PREV)
    omitted = resolve_affect(_PREV, {}, None, 1, {"surface": {"label": "anxious"}})
    cleared = resolve_affect(_PREV, {}, None, 1, {
        "surface": {"label": "anxious"}, "undercurrent": None})

    assert -0.5 < omitted["undercurrent"]["valence"] < 0
    assert cleared["undercurrent"] is None
    assert omitted["surface"] == cleared["surface"]
    assert _PREV == before


def test_explicit_null_prevents_fresh_contradiction_from_synthesizing_residue():
    appraisal = appraise([{"serves": "drive", "impact": -0.9, "certainty": 0.9,
                          "agency": "other", "why": "the stolen letter was read aloud"}],
                        lambda _serves: 1.0)
    omitted = resolve_affect(_PREV, appraisal, None, 0, {"surface": {"label": "cheerful"}})
    cleared = resolve_affect(_PREV, appraisal, None, 0, {
        "surface": {"label": "cheerful"}, "undercurrent": None})

    assert omitted["undercurrent"]["source"] == "the stolen letter was read aloud"
    assert cleared["undercurrent"] is None
    assert cleared["surface"] == omitted["surface"]


@pytest.mark.parametrize("serves,clears", [("i1", True), ("i2", False)])
def test_omitted_undercurrent_keeps_existing_goal_specific_relief(serves, clears):
    appraisal = appraise([{"serves": serves, "impact": 0.9, "certainty": 1.0,
                          "agency": "other", "why": "a confirmed win"}],
                        lambda _serves: 1.0)
    result = resolve_affect(_PREV, appraisal, None, 1, {})
    assert (result["undercurrent"] is None) is clears
