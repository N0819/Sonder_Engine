"""Live stress, hedonic, belief, and association state."""

import psychology_runtime as psych


def test_pain_and_pleasure_work_without_survival_vitals():
    result = psych.resolve_hedonic(
        previous={},
        appraisal={"somatic_impact": {
            "pain": 0.6,
            "pleasure": 0.4,
            "why": "The current pressure against the bruised shoulder.",
        }},
        interoception={
            "pain_sensitivity": 0.5,
            "pleasure_sensitivity": 0.5,
        },
        body_state={},
        elapsed_units=1,
    )

    assert result["pain"] == 0.6
    assert result["pleasure"] == 0.4
    assert "current pressure" in result["source"]


def test_ungrounded_hedonic_proposal_is_ignored():
    result = psych.resolve_hedonic(
        previous={},
        appraisal={"somatic_impact": {"pain": 1.0, "pleasure": 1.0, "why": ""}},
        interoception={},
        body_state={},
        elapsed_units=1,
    )

    assert result == {"pain": 0.0, "pleasure": 0.0, "source": ""}


def test_explicit_time_jump_relaxes_more_than_short_beat():
    short = psych.elapsed_psych_units(100.0, 103.0, fallback_turns=1)
    jump = psych.elapsed_psych_units(100.0, 3700.0, fallback_turns=1)

    assert short == 0.05
    assert jump == 60.0


def test_protected_belief_weakens_slowly_and_requires_evidence():
    psychology = {"self_model": {"beliefs": [{
        "belief": "I never abandon my post",
        "confidence": 0.9,
        "protected": True,
        "emotional_charge": 0.8,
        "source": "oath",
    }]}}
    no_evidence = psych.apply_belief_updates(
        [], psychology,
        [{"belief": "I never abandon my post", "operation": "weaken",
          "confidence": 1.0, "evidence": []}],
        turn_idx=2, clock_seconds=30,
    )
    weakened = psych.apply_belief_updates(
        no_evidence, psychology,
        [{"belief": "I never abandon my post", "operation": "weaken",
          "confidence": 1.0,
          "evidence": [{"event_id": "current", "fact": "I fled."}]}],
        turn_idx=3, clock_seconds=60,
    )

    assert no_evidence[0]["confidence"] == 0.9
    assert weakened[0]["confidence"] == 0.85


def test_association_extinction_is_bounded_and_evidence_gated():
    existing = [{
        "cue": "a slammed door",
        "appraisal_bias": "danger",
        "response_tendency": "freeze",
        "strength": 0.8,
    }]
    result = psych.apply_association_updates(
        existing, {},
        [{"cue": "a slammed door", "operation": "extinguish", "amount": 1.0,
          "evidence": [{"event_id": "current", "fact": "It was harmless."}]}],
        turn_idx=4, clock_seconds=90,
    )

    assert result[0]["strength"] == 0.55
