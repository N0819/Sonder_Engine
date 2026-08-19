"""Live stress, hedonic, belief, and association state."""

from mind import psychology_runtime as psych


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
                      "charge": 0.0, "saturated": False,
                      "sustained_beats": 0.0, "stimulus": 0.0}


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


def test_remembered_threat_is_mild_and_labelled_beside_current_stress():
    plain = psych.resolve_stress(
        previous={}, appraisal={}, profile={"baseline_reactivity": 1.0},
        hedonic={}, elapsed_units=1)
    remembered = psych.resolve_stress(
        previous={}, appraisal={"memory_echo": {"threat_bias": 0.2}},
        profile={"baseline_reactivity": 1.0},
        hedonic={}, elapsed_units=1)
    present = psych.resolve_stress(
        previous={}, appraisal={
            "goal_impacts": [{"impact": -0.5, "certainty": 1.0}]},
        profile={"baseline_reactivity": 1.0},
        hedonic={}, elapsed_units=1)

    assert remembered["strain"] > plain["strain"]
    assert remembered["strain"] < present["strain"]
    assert remembered["memory_threat_bias"] == 0.2
    assert remembered["overloaded"] is False


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


def test_contradicting_an_unheld_belief_does_not_assert_it():
    """Denying something is not holding it.

    The mint branch read `confidence` and never `operation`, so a contradiction
    of a belief the character does not hold WROTE that belief into their
    ledger, at the strength of the evidence against it. The character came out
    of the beat believing the thing the beat disproved.
    """
    minted = psych.apply_belief_updates(
        [], {},
        [{"belief": "the north stair is safe", "operation": "contradict",
          "confidence": 0.9,
          "evidence": [{"event_id": "current", "fact": "It gave way."}]}],
        turn_idx=2, clock_seconds=30,
    )

    held = [item for item in minted
            if item["belief"] == "the north stair is safe"]
    assert not held or held[0]["confidence"] <= 0.5, minted


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


def test_the_belief_cap_never_evicts_what_the_sheet_re_seeds():
    """A bound that the next turn undoes is not a bound, it is amnesia.

    The cap sliced the LAST twenty, and the front of the list is where the
    seeding pass puts the beliefs the card authored. So the entry evicted was
    an authored one; the next turn found it missing from the ledger and
    re-seeded it from the sheet at card confidence with last_updated_turn 0,
    throwing away every revision the story had earned on it -- and pushed a
    learned belief out to make room for the resurrection.
    """
    psychology = {"self_model": {"beliefs": [{
        "belief": "I never abandon my post",
        "confidence": 0.9,
        "protected": True,
    }]}}
    state = psych.apply_belief_updates(
        [], psychology,
        [{"belief": "I never abandon my post", "operation": "weaken",
          "confidence": 1.0,
          "evidence": [{"event_id": "current", "fact": "I fled."}]}],
        turn_idx=1, clock_seconds=10,
    )
    earned = state[0]["confidence"]
    assert earned < 0.9

    for n in range(25):
        state = psych.apply_belief_updates(
            state, psychology,
            [{"belief": f"learned thing {n}", "confidence": 0.6,
              "evidence": [{"event_id": "current", "fact": "seen"}]}],
            turn_idx=2 + n, clock_seconds=20 + n,
        )

    held = {item["belief"]: item for item in state}
    assert "I never abandon my post" in held
    assert abs(held["I never abandon my post"]["confidence"] - earned) < 1e-9


def test_the_association_cap_never_evicts_what_the_sheet_re_seeds():
    """Same shape, same file, one line apart -- authored associations are
    re-seeded from `learning.associations` every turn, so evicting one costs a
    learned slot and restores the card's strength."""
    psychology = {"learning": {"associations": [{
        "cue": "a slammed door",
        "appraisal_bias": "danger",
        "response_tendency": "freeze",
        "strength": 0.8,
    }]}}
    state = psych.apply_association_updates(
        [], psychology,
        [{"cue": "a slammed door", "operation": "extinguish", "amount": 0.25,
          "evidence": [{"event_id": "current", "fact": "It was harmless."}]}],
        turn_idx=1, clock_seconds=10,
    )
    earned = state[0]["strength"]
    assert earned < 0.8

    for n in range(25):
        state = psych.apply_association_updates(
            state, psychology,
            [{"cue": f"cue {n}", "amount": 0.1,
              "evidence": [{"event_id": "current", "fact": "seen"}]}],
            turn_idx=2 + n, clock_seconds=20 + n,
        )

    held = {item["cue"]: item for item in state}
    assert "a slammed door" in held
    assert abs(held["a slammed door"]["strength"] - earned) < 1e-9


class TestSustainedLevelHabituation:
    """The pain/pleasure LEVEL is peak-held, so a body under continuous strong
    stimulus reads at the ceiling indefinitely -- and cognitive_absorption read
    that level, handing back full absorption forever with it. Measured live: a
    character held there could hold exactly one open question, produced no new
    want for three straight beats, and said the same sentence shape every time.

    Beat twelve of maximum stimulation does not claim a mind the way beat one
    does. But a PEAK still does, so habituation covers the plateau and never
    the spike.
    """

    def _beat(self, previous, pleasure, novelty=0.0, released=False):
        return psych.resolve_hedonic(
            previous,
            {"somatic_impact": {"pain": 0.0, "pleasure": pleasure,
                                "why": "sustained contact"},
             "novelty": novelty},
            {"pleasure_sensitivity": 0.5}, {}, 1.0, released=released,
        )

    def test_a_plateau_stops_being_arresting(self):
        state = self._beat({}, 0.9)
        first = psych.cognitive_absorption(state)
        for _ in range(6):
            state = self._beat(state, 0.9)

        assert state["sustained_beats"] > 0
        assert psych.cognitive_absorption(state) < first

    def test_habituation_settles_at_busy_not_free(self):
        """A saturated body habituates to "three thoughts", never to "free"."""
        state = self._beat({}, 0.95)
        for _ in range(20):
            state = self._beat(state, 0.95)

        assert state["saturated"] is True
        assert psych.cognitive_absorption(state) >= psych._ABSORPTION_SATURATED_FLOOR

    def test_a_fresh_escalation_is_fully_arresting_again(self):
        state = self._beat({}, 0.6)
        for _ in range(8):
            state = self._beat(state, 0.6)
        plateaued = psych.cognitive_absorption(state)

        state = self._beat(state, 0.95)          # the spike

        assert state["sustained_beats"] == 0.0
        assert psych.cognitive_absorption(state) > plateaued

    def test_a_novel_beat_also_resets_the_clock(self):
        state = self._beat({}, 0.9)
        for _ in range(6):
            state = self._beat(state, 0.9)
        assert state["sustained_beats"] > 0

        state = self._beat(state, 0.9, novelty=0.85)
        assert state["sustained_beats"] == 0.0

    def test_release_resets_the_clock(self):
        state = self._beat({}, 0.9)
        for _ in range(6):
            state = self._beat(state, 0.9)

        state = self._beat(state, 0.9, released=True)
        assert state["sustained_beats"] == 0.0
        assert state["charge"] == 0.0

    def test_jitter_on_the_plateau_is_not_a_peak(self):
        """Small wobble is the same plateau, not a new event."""
        state = self._beat({}, 0.88)
        for pleasure in (0.85, 0.9, 0.86, 0.92, 0.89):
            state = self._beat(state, pleasure)

        assert state["sustained_beats"] > 0

    def test_a_level_that_falls_away_clears_the_clock(self):
        state = self._beat({}, 0.9)
        for _ in range(5):
            state = self._beat(state, 0.9)

        for _ in range(8):
            state = self._beat(state, 0.0)
        assert state["sustained_beats"] == 0.0

    def test_a_state_saved_before_habituation_existed_reads_as_fresh(self):
        legacy = {"pain": 0.0, "pleasure": 0.95, "charge": 0.9,
                  "saturated": True}
        assert psych.cognitive_absorption(legacy) == psych.cognitive_absorption(
            {**legacy, "sustained_beats": 0.0})

    def test_absorption_is_total_on_junk(self):
        for junk in (None, "lots", -4, {"sustained_beats": "many"}):
            value = psych.cognitive_absorption(
                junk if isinstance(junk, dict) else {"pleasure": 0.5,
                                                     "sustained_beats": junk})
            assert 0.0 <= value <= 1.0
