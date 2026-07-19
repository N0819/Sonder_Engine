"""Unit tests for theory_of_mind.py belief revision.

Pure-function tests: no DB, no LLM calls. These pin down the behavior
that replaced the old exact-text-keyed max()-only accumulation in
commit.py -- reinforcement blends toward new evidence, competing claims
suppress but don't erase each other, decay differs by kind, and stale
beliefs are pruned rather than accumulating forever.
"""

from theory_of_mind import (
    apply_mind_model_updates,
    claim_similarity,
    decayed_confidence,
    mind_models_for_payload,
)

def test_reinforcement_blends_toward_new_evidence_not_max():
    state = {}
    state = apply_mind_model_updates(state, [{
        "about_entity": "Rowan", "kind": "goal",
        "claim": "wants to leave the lighthouse",
        "confidence": 0.3, "evidence": [],
    }], turn_idx=0)

    state = apply_mind_model_updates(state, [{
        "about_entity": "Rowan", "kind": "goal",
        "claim": "wants to leave the lighthouse tonight",
        "confidence": 0.8, "evidence": [],
    }], turn_idx=1)

    hyps = state["mind_models"]["Rowan"]["hypotheses"]
    assert len(hyps) == 1, "a reworded restatement should reinforce, not duplicate"
    assert 0.3 < hyps[0]["confidence"] < 0.8, (
        "confidence should move toward the new evidence, not jump straight to it"
    )

def test_competing_claim_suppresses_but_does_not_erase():
    state = {}
    state = apply_mind_model_updates(state, [{
        "about_entity": "Mara", "kind": "goal",
        "claim": "wants to protect the keeper's logbook",
        "confidence": 0.6, "evidence": [],
    }], turn_idx=0)

    state = apply_mind_model_updates(state, [{
        "about_entity": "Mara", "kind": "goal",
        "claim": "wants to sabotage the radio tower",
        "confidence": 0.9, "evidence": [],
    }], turn_idx=1)

    hyps = state["mind_models"]["Mara"]["hypotheses"]
    assert len(hyps) == 2, "a genuinely different claim should compete, not overwrite"
    original = next(h for h in hyps if "logbook" in h["claim"])
    assert 0.0 < original["confidence"] < 0.6, (
        "a strong competing claim should weaken the original belief without zeroing it"
    )

def test_decay_differs_by_kind():
    # observation (half-life 5) should fade far faster than trait (half-life 400)
    # over the same elapsed turns, from the same starting confidence.
    observation_decayed = decayed_confidence(0.8, "observation", 20)
    trait_decayed = decayed_confidence(0.8, "trait", 20)
    assert observation_decayed < trait_decayed
    assert observation_decayed < 0.8 * 0.2  # substantially faded
    assert trait_decayed > 0.8 * 0.9  # barely moved

def test_decay_half_life_is_exact_at_one_half_life():
    result = decayed_confidence(0.8, "observation", 5)  # half-life of observation is 5
    assert abs(result - 0.4) < 1e-9

def test_decay_no_elapsed_turns_is_a_noop():
    assert decayed_confidence(0.6, "emotion", 0) == 0.6

def test_pruning_removes_entity_once_all_hypotheses_decay_below_floor():
    state = {
        "mind_models": {
            "Ghost": {
                "hypotheses": [{
                    "about_entity": "Ghost", "kind": "emotion",
                    "claim": "seemed afraid", "confidence": 0.2,
                    "evidence": [], "last_updated_turn": 0,
                }],
            }
        }
    }
    # emotion half-life is 6 turns; 100 elapsed turns should decay this well
    # below the default 0.05 floor.
    state = apply_mind_model_updates(state, [], turn_idx=100)
    assert "Ghost" not in state["mind_models"]

def test_top_cap_still_enforced_after_decay():
    hyps = [{
        "about_entity": "Crowd", "kind": "trait",
        "claim": f"trait claim number {i} about them",
        "confidence": 0.9, "evidence": [], "last_updated_turn": 0,
    } for i in range(35)]
    state = {"mind_models": {"Crowd": {"hypotheses": hyps}}}
    state = apply_mind_model_updates(state, [], turn_idx=0)
    assert len(state["mind_models"]["Crowd"]["hypotheses"]) <= 30

def test_claim_similarity_subset_is_treated_as_same_belief():
    a = "is hiding something"
    b = "seems to be hiding something about the letter she received"
    assert claim_similarity(a, b) == 1.0

def test_claim_similarity_unrelated_claims_score_zero():
    a = "wants to leave the island"
    b = "fears the lighthouse keeper"
    assert claim_similarity(a, b) == 0.0

def test_mind_models_for_payload_surfaces_leading_and_competitors():
    state = {}
    state = apply_mind_model_updates(state, [{
        "about_entity": "Mara", "kind": "goal",
        "claim": "wants to protect the keeper's logbook",
        "confidence": 0.6, "evidence": [],
    }], turn_idx=0)
    state = apply_mind_model_updates(state, [{
        "about_entity": "Mara", "kind": "goal",
        "claim": "wants to sabotage the radio tower",
        "confidence": 0.9, "evidence": [],
    }], turn_idx=1)

    payload = mind_models_for_payload(state["mind_models"], turn_idx=1)
    goal_view = payload["Mara"]["goal"]
    assert "sabotage" in goal_view["leading"]["claim"]
    assert len(goal_view["competitors"]) == 1
    assert "logbook" in goal_view["competitors"][0]["claim"]
    assert goal_view["leading"]["confidence"] >= goal_view["competitors"][0]["confidence"]
