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

    assert result == {"pain": 0.0, "pleasure": 0.0, "source": "",
                      "charge": 0.0, "saturated": False}


def _sustained(beats, previous=None, released_on=None, pleasure=0.9):
    """Run `beats` beats of the same strong stimulus through the runtime."""
    state = previous or {}
    for beat in range(beats):
        state = psych.resolve_hedonic(
            previous=state,
            appraisal={"somatic_impact": {
                "pain": 0.0, "pleasure": pleasure,
                "why": "the same unbroken pressure",
            }},
            interoception={"pleasure_sensitivity": 0.9},
            body_state={},
            elapsed_units=1,
            released=(beat == released_on),
        )
    return state


def test_sustained_stimulus_accumulates_where_the_level_cannot():
    """The level clamps at the ceiling on beat one, so it says nothing about a
    stimulus that has been building for ten beats; the charge does."""
    early = _sustained(1)
    late = _sustained(10)

    assert early["pleasure"] == late["pleasure"] == 1.0
    assert late["charge"] > early["charge"]
    assert late["saturated"] is True
    assert early["saturated"] is False


def test_only_the_character_can_discharge_the_charge():
    held = _sustained(10)
    released = _sustained(11, released_on=10)

    assert held["charge"] > 0.8
    assert released["charge"] == 0.0
    assert released["saturated"] is False


def test_charge_outlives_the_level_it_came_from():
    """Stimulus stops: the level falls away fast, the pressure it built does
    not vanish with it."""
    built = _sustained(8)
    quiet = psych.resolve_hedonic(
        previous=built, appraisal={}, interoception={}, body_state={},
        elapsed_units=4,
    )

    assert quiet["pleasure"] < 0.3
    assert quiet["charge"] > 0.5


def test_intense_pleasure_no_longer_reads_as_perfect_composure():
    """All-positive appraisal at the ceiling of a sustained stimulus used to
    produce activation and load of exactly zero."""
    hedonic = _sustained(10)
    stress = psych.resolve_stress(
        previous={}, appraisal={
            "novelty": 0.75, "controllability": 0.8, "coping_potential": 0.85,
            "norm_compatibility": 0.9,
            "goal_impacts": [{"impact": 0.9, "certainty": 0.9}],
        },
        profile={"baseline_reactivity": 0.65},
        hedonic=hedonic, elapsed_units=1,
    )

    assert stress["activation"] > 0.5
    # ...but a demanding drive is not a coping failure.
    assert stress["overloaded"] is False
    assert stress["strain"] < 0.2


def test_pleasure_still_damps_cumulative_load():
    pleasant = psych.resolve_stress(
        previous={"load": 0.4}, appraisal={"somatic_impact": {}},
        profile={}, hedonic={"pleasure": 0.9}, elapsed_units=1)
    plain = psych.resolve_stress(
        previous={"load": 0.4}, appraisal={"somatic_impact": {}},
        profile={}, hedonic={}, elapsed_units=1)

    assert pleasant["load"] <= plain["load"]


def test_threat_still_drives_strain_and_overload():
    stress = psych.resolve_stress(
        previous={}, appraisal={
            "novelty": 0.9, "controllability": 0.1, "coping_potential": 0.1,
            "goal_impacts": [{"impact": -0.9, "certainty": 1.0}],
        },
        profile={"baseline_reactivity": 1.0, "overload_threshold": 0.6},
        hedonic={"pain": 0.7}, elapsed_units=1)

    assert stress["strain"] >= 0.6
    assert stress["overloaded"] is True


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
