"""Tests for the deterministic interior-state floors in affect.py.

Everything under test is pure (no DB), so these are plain functions with
no fixtures: lexicon/label consistency, OCC appraisal mapping, mood
inertia and decay, undercurrent synthesis and relief, want normalization,
intention-op guards, leak scanning, and the tell gate.
"""

from itertools import product

import pytest

from affect import (
    AFFECT_LEXICON,
    _va_pair,
    appraise,
    apply_intent_ops,
    blend_affect,
    decay_affect,
    detect_drive_rupture,
    former_drive_entry,
    label_matches,
    leak_scan,
    normalize_serves,
    normalize_wants,
    quadrant_label,
    resolve_affect,
    tell_gate,
    update_drive_strain,
    validate_drive_shift,
)

def _priority_of(serves, ids=("i1",)):
    if serves == "drive":
        return 1.0
    if serves in ids:
        return 0.8
    return 0.4

# ---- Lexicon / labels ----

def test_label_matches_agrees_and_contradicts():
    assert label_matches("happy", 0.5, 0.5)
    assert not label_matches("happy", -0.5, 0.5)   # positive label, negative valence
    assert not label_matches("grief", 0.5, 0.5)
    # a lexicon 0 axis is unopinionated; a near-zero observed axis contradicts nothing
    assert label_matches("wary", -0.5, 0.0)
    assert label_matches("content", 0.5, 0.02)

def test_unknown_label_is_never_rejected():
    assert label_matches("saudade", -1.0, -1.0)
    assert label_matches("", 0.7, 0.7)
    assert label_matches(None, -0.7, 0.7)

def test_quadrant_labels_are_lexicon_consistent():
    for v, a in product((-0.5, 0.0, 0.5), repeat=2):
        label = quadrant_label(v, a)
        assert label in AFFECT_LEXICON
        assert label_matches(label, v, a)

def test_lexicon_signs_are_valid():
    for label, entry in AFFECT_LEXICON.items():
        assert entry["v"] in (-1, 0, 1), label
        assert entry["a"] in (-1, 0, 1), label

# ---- Appraisal ----

def test_appraise_empty_is_zero():
    out = appraise([], _priority_of)
    assert out == {"dV": 0.0, "dA": 0.0, "emotions": [], "dominant": None,
                   "drive_impact": None}
    assert appraise(None, _priority_of)["dV"] == 0.0

def test_appraise_uncertain_threat_is_fear():
    out = appraise([{"serves": "drive", "impact": -0.6, "certainty": 0.5,
                     "agency": "none", "why": "footsteps upstairs"}], _priority_of)
    assert out["emotions"] == ["fear"]
    assert out["dV"] == pytest.approx(-0.15)   # 0.5 * -0.6 * 0.5 * 1.0
    assert out["dA"] == pytest.approx(0.12)    # fear mobilizes: 0.4 * 0.3
    assert out["dominant"]["why"] == "footsteps upstairs"

def test_appraise_certain_loss_splits_on_agency():
    other = appraise([{"serves": "drive", "impact": -0.5, "certainty": 0.9,
                       "agency": "other", "why": "he burned it"}], _priority_of)
    nobody = appraise([{"serves": "drive", "impact": -0.5, "certainty": 0.9,
                        "agency": "none", "why": "the storm took it"}], _priority_of)
    assert other["emotions"] == ["anger"]
    assert other["dA"] > 0
    assert nobody["emotions"] == ["sadness"]
    assert nobody["dA"] < 0                    # sadness stands down

def test_appraise_positive_splits_on_certainty():
    hope = appraise([{"serves": "drive", "impact": 0.5, "certainty": 0.5,
                      "agency": "self", "why": "a lead"}], _priority_of)
    done = appraise([{"serves": "drive", "impact": 0.8, "certainty": 1.0,
                      "agency": "self", "why": "it worked"}], _priority_of)
    assert hope["emotions"] == ["hope"]
    assert hope["dA"] == pytest.approx(0.05)   # hope lifts only slightly
    assert done["emotions"] == ["satisfaction"]
    assert done["dA"] < 0                      # confirmed gain relaxes

def test_appraise_orders_emotions_and_picks_dominant():
    out = appraise([
        {"serves": "situational", "impact": 0.2, "certainty": 0.5,
         "agency": "none", "why": "nice weather"},
        {"serves": "drive", "impact": -0.9, "certainty": 0.9,
         "agency": "other", "why": "the betrayal"},
    ], _priority_of)
    assert out["emotions"][0] == "anger"       # heavier weight sorts first
    assert out["dominant"]["why"] == "the betrayal"

def test_appraise_is_total_on_junk():
    out = appraise([{"serves": None, "impact": "much", "certainty": None},
                    "not a dict"], _priority_of)
    assert out["dV"] == 0.0 and out["dominant"] is None

    def broken(serves):
        raise ValueError("no table for you")
    out = appraise([{"serves": "drive", "impact": -1.0, "certainty": 1.0,
                     "agency": "other", "why": "x"}], broken)
    assert out["emotions"] == ["anger"]        # falls back to situational priority

# ---- Point coercion ----

def test_va_pair_reads_canonical_legacy_and_tuple():
    assert _va_pair({"valence": -0.3, "arousal": 0.6}) == (-0.3, 0.6)
    assert _va_pair({"v": -0.3, "a": 0.6}) == (-0.3, 0.6)      # legacy keys
    assert _va_pair((-0.3, 0.6)) == (-0.3, 0.6)                # tuple
    assert _va_pair([0.2, 0.1]) == (0.2, 0.1)                  # list
    # canonical key wins when both spellings appear
    assert _va_pair({"valence": 0.5, "v": -0.5}) == (0.5, 0.0)
    # clamped, and total on junk
    assert _va_pair({"valence": 2.0, "arousal": -2.0}) == (1.0, -1.0)
    assert _va_pair(None) == (0.0, 0.0)
    assert _va_pair("guarded") == (0.0, 0.0)

# ---- Blend / decay ----

def test_blend_inertia_clamp_and_shock():
    # arousal 1.0 -> plasticity 0.65, raw step 0.65, clamped to 0.4
    assert blend_affect((0.0, 0.0), (1.0, 1.0), 1.0) == (0.4, 0.4)
    v, a = blend_affect((0.0, 0.0), (1.0, 1.0), 1.0, shock=True)
    assert v == pytest.approx(0.65) and a == pytest.approx(0.65)

def test_blend_plasticity_bounds():
    # very negative arousal floors plasticity at 0: mood is frozen
    assert blend_affect((0.0, 0.0), (1.0, 1.0), -2.0) == (0.0, 0.0)
    # extreme arousal caps plasticity at 0.9 and output stays in [-1, 1]
    v, a = blend_affect((0.9, 0.9), (1.0, 1.0), 5.0, shock=True)
    assert -1.0 <= v <= 1.0 and -1.0 <= a <= 1.0

def test_decay_halves_distance_per_half_life():
    assert decay_affect((1.0, -1.0), (0.0, 0.0), 8) == (0.5, -0.5)
    v, a = decay_affect((1.0, 0.0), (0.2, 0.2), 8)
    assert v == pytest.approx(0.6) and a == pytest.approx(0.1)
    assert decay_affect((0.7, -0.3), (0.0, 0.0), 0) == (0.7, -0.3)

# ---- resolve_affect ----

_NEUTRAL_PREV = {"surface": {"label": "neutral", "valence": 0.0, "arousal": 0.0},
                 "undercurrent": None,
                 "baseline": {"valence": 0.0, "arousal": 0.0}}
_ZERO_BASE = {"valence": 0.0, "arousal": 0.0}

def test_happy_label_under_negative_appraisal_synthesizes_undercurrent():
    # the model gave only a label and NO undercurrent: the engine still
    # synthesizes one when the label contradicts a strong appraisal
    appraisal = appraise([{"serves": "drive", "impact": -0.9, "certainty": 0.9,
                           "agency": "other",
                           "why": "he read the stolen letter aloud"}], _priority_of)
    out = resolve_affect(_NEUTRAL_PREV, appraisal, _ZERO_BASE, 0, "cheerful")
    # the self-report is kept on the surface, but the numbers tell the truth
    assert out["surface"]["label"] == "cheerful"
    assert out["surface"]["valence"] < 0
    assert out["undercurrent"] is not None
    assert out["undercurrent"]["label"] == "anger"
    assert out["undercurrent"]["valence"] < 0
    assert "letter" in out["undercurrent"]["source"]

def test_matching_label_produces_no_undercurrent():
    appraisal = appraise([{"serves": "drive", "impact": -0.9, "certainty": 0.9,
                           "agency": "other", "why": "the betrayal"}], _priority_of)
    out = resolve_affect(_NEUTRAL_PREV, appraisal, _ZERO_BASE, 0, "angry")
    assert out["surface"]["label"] == "angry"
    assert out["undercurrent"] is None

def test_bare_mood_string_proposal_still_works():
    appraisal = appraise([{"serves": "drive", "impact": -0.5, "certainty": 0.5,
                           "agency": "none", "why": "footsteps upstairs"}], _priority_of)
    out = resolve_affect(_NEUTRAL_PREV, appraisal, _ZERO_BASE, 0, "nervous")
    assert out["surface"]["label"] == "nervous"
    assert out["surface"]["valence"] < 0
    assert out["surface"]["arousal"] > 0
    assert out["undercurrent"] is None         # label agrees: nothing suppressed
    assert set(out["surface"]) == {"label", "valence", "arousal"}

def test_resolve_adopts_model_proposed_surface_and_undercurrent():
    # the live-sweep emission: guarded surface over a fearful undercurrent
    proposed = {
        "surface": {"label": "guarded", "valence": -0.3, "arousal": 0.6},
        "undercurrent": {"label": "fearful", "valence": -0.7, "arousal": 0.8},
        "baseline": {"valence": 0.1, "arousal": 0.3},
    }
    appraisal = appraise([{"serves": "drive", "impact": -0.4, "certainty": 0.5,
                           "agency": "other", "why": "the stranger keeps watching"}],
                         _priority_of)
    out = resolve_affect(_NEUTRAL_PREV, appraisal,
                         {"valence": 0.1, "arousal": 0.3}, 0, proposed)
    # not flattened to neutral: the authored affect survives the floors
    assert out["surface"]["label"] == "guarded"
    assert out["surface"]["valence"] < 0
    assert out["surface"]["arousal"] > 0
    assert out["undercurrent"] is not None
    assert out["undercurrent"]["label"] == "fearful"
    assert out["undercurrent"]["valence"] == pytest.approx(-0.7)
    assert out["undercurrent"]["arousal"] == pytest.approx(0.8)
    # canonical keys throughout — no legacy v/a on outputs
    assert "v" not in out["surface"] and "a" not in out["surface"]
    assert "v" not in out["undercurrent"] and "a" not in out["undercurrent"]
    assert out["baseline"] == {"valence": 0.1, "arousal": 0.3}

def test_relief_clears_model_proposed_undercurrent():
    proposed = {
        "surface": {"label": "relieved", "valence": 0.4, "arousal": -0.2},
        "undercurrent": {"label": "fearful", "valence": -0.6, "arousal": 0.7,
                         "source": "the guard suspects her", "serves": "i1"},
    }
    appraisal = appraise([{"serves": "i1", "impact": 0.9, "certainty": 1.0,
                           "agency": "other",
                           "why": "the guard waved her through"}], _priority_of)
    out = resolve_affect(_NEUTRAL_PREV, appraisal, _ZERO_BASE, 0, proposed)
    assert out["undercurrent"] is None         # the confirmed win dissolves the dread
    assert out["surface"]["label"] == "relieved"
    assert out["surface"]["valence"] > 0

def test_relief_clears_undercurrent():
    prev = {"surface": {"label": "anxious", "valence": -0.4, "arousal": 0.3},
            "undercurrent": {"label": "fear", "valence": -0.5, "arousal": 0.4,
                             "source": "the guard suspects her", "serves": "i1"},
            "baseline": {"valence": 0.0, "arousal": 0.0}}
    appraisal = appraise([{"serves": "i1", "impact": 0.9, "certainty": 1.0,
                           "agency": "other",
                           "why": "the guard waved her through"}], _priority_of)
    out = resolve_affect(prev, appraisal, _ZERO_BASE, 1, None)
    assert out["undercurrent"] is None
    assert out["surface"]["valence"] > -0.4    # mood moved toward the good news

def test_unrelated_good_news_only_decays_undercurrent():
    # prior residue deliberately kept on legacy v/a keys: read tolerantly,
    # written back canonically
    prev = {"surface": {"label": "anxious", "v": -0.4, "a": 0.3},
            "undercurrent": {"label": "fear", "v": -0.5, "a": 0.4,
                             "source": "the guard suspects her", "serves": "i1"},
            "baseline": {"v": 0.0, "a": 0.0}}
    appraisal = appraise([{"serves": "situational", "impact": 0.9, "certainty": 1.0,
                           "agency": "other", "why": "free ale tonight"}], _priority_of)
    out = resolve_affect(prev, appraisal, _ZERO_BASE, 1, None)
    assert out["undercurrent"] is not None     # wrong goal: no relief
    assert abs(out["undercurrent"]["valence"]) < 0.5  # but it decays on half_life 4
    assert "v" not in out["undercurrent"]

def test_pure_decay_when_nothing_happens():
    prev = {"surface": {"label": "happy", "valence": 0.8, "arousal": 0.0},
            "undercurrent": None, "baseline": {"valence": 0.0, "arousal": 0.0}}
    out = resolve_affect(prev, None, _ZERO_BASE, 8, None)
    assert out["surface"]["valence"] == pytest.approx(0.4)  # one half-life toward baseline
    assert out["surface"]["label"] == "happy"  # label still fits the numbers
    assert out["undercurrent"] is None

def test_stale_undercurrent_fades_below_floor():
    prev = {"surface": {"label": "neutral", "valence": 0.0, "arousal": 0.0},
            "undercurrent": {"label": "fear", "valence": -0.2, "arousal": 0.1,
                             "source": "old scare", "serves": "i1"},
            "baseline": {"valence": 0.0, "arousal": 0.0}}
    out = resolve_affect(prev, None, _ZERO_BASE, 8, None)
    assert out["undercurrent"] is None         # -0.2 * 0.5**2 = -0.05, under floor

def test_resolve_is_total_on_junk_and_fully_populated():
    out = resolve_affect(None, None, None, None, None)
    assert set(out) == {"surface", "undercurrent", "baseline"}
    assert set(out["surface"]) == {"label", "valence", "arousal"}
    assert out["surface"]["label"] == "neutral"
    assert out["baseline"] == {"valence": 0.0, "arousal": 0.0}

# ---- Wants ----

def test_normalize_wants_dedup_serves_and_selection():
    wants = [
        {"want": "learn the courier's route", "urgency": 0.9, "serves": "i1"},
        # near-duplicate of the first: merged, higher urgency kept
        {"want": "learn the courier's exact route tonight", "urgency": 0.7, "serves": "i1"},
        # unknown serves -> situational
        {"want": "impress the captain", "urgency": 0.6, "serves": "bogus"},
        # second situational: dropped (lower urgency)
        {"want": "sample the wine", "urgency": 0.3, "serves": "nah"},
        {"want": "avoid the courier entirely", "urgency": 0.8, "serves": "drive",
         "conflicts_with": "learn the courier's route"},
    ]
    out, enacted_idx, suppressed_idx = normalize_wants(wants, {"i1"})
    assert len(out) == 3
    assert [w["want"] for w in out] == [
        "learn the courier's route", "impress the captain", "avoid the courier entirely"]
    assert out[0]["urgency"] == 0.9            # merge kept the max urgency
    assert out[1]["serves"] == "situational"
    assert enacted_idx == 0 and out[0]["enacted"]
    assert suppressed_idx == 2 and out[2]["suppressed"]

def test_normalize_wants_caps_at_three_by_urgency():
    wants = [
        {"want": "guard the door", "urgency": 0.9, "serves": "drive"},
        {"want": "polish armor daily", "urgency": 0.5, "serves": "drive"},
        {"want": "write mother a letter", "urgency": 0.7, "serves": "drive"},
        {"want": "practice swordwork forms", "urgency": 0.8, "serves": "drive"},
    ]
    out, enacted_idx, suppressed_idx = normalize_wants(wants, set())
    assert len(out) == 3
    assert all(w["want"] != "polish armor daily" for w in out)
    assert out[enacted_idx]["want"] == "guard the door"
    assert suppressed_idx is None              # nothing declared a conflict

def test_normalize_wants_empty_and_junk():
    assert normalize_wants([], set()) == ([], None, None)
    assert normalize_wants(["oops", {"urgency": 1.0}], set()) == ([], None, None)

# ---- Intentions ----

def _ok(_op):
    return True

def _no(_op):
    return False

def test_intent_add_assigns_deterministic_ids():
    out, warnings = apply_intent_ops(
        [], [{"op": "add", "intent": "win the guard's trust",
              "serves_drive": "belonging"}], 10, _ok)
    assert warnings == []
    assert out[0]["id"] == "i1"
    assert out[0]["status"] == "active"
    assert out[0]["formed_turn"] == 10 and out[0]["progress"] == 0.0

def test_intent_duplicate_add_becomes_progress():
    base, _ = apply_intent_ops(
        [], [{"op": "add", "intent": "win the guard's trust"}], 10, _ok)
    out, warnings = apply_intent_ops(
        base, [{"op": "add", "intent": "win the trust of the guard"}], 12, _ok)
    assert warnings == []
    assert len(out) == 1                       # rephrasing is progress, not a new goal
    assert out[0]["progress"] == pytest.approx(0.2)
    assert out[0]["last_progress_turn"] == 12

def test_intent_cap_rejects_fifth_active():
    intents = []
    for text in ("escape the city", "find her brother",
                 "repay the debt", "map the sewers"):
        intents, _ = apply_intent_ops(
            intents, [{"op": "add", "intent": text}], 5, _ok)
    out, warnings = apply_intent_ops(
        intents, [{"op": "add", "intent": "steal a horse"}], 6, _ok)
    assert len(out) == 4
    assert any("cap" in w for w in warnings)

def test_intent_early_satisfy_requires_evidence():
    base, _ = apply_intent_ops(
        [], [{"op": "add", "intent": "escape the city"}], 10, _ok)
    # 2 turns old, no evidence: rejected
    out, warnings = apply_intent_ops(
        base, [{"op": "satisfy", "id": "i1"}], 12, _no)
    assert out[0]["status"] == "active"
    assert any("evidence" in w for w in warnings)
    # same turn, with evidence: accepted
    out, warnings = apply_intent_ops(
        base, [{"op": "satisfy", "id": "i1", "evidence": "she is outside the walls"}],
        12, _ok)
    assert out[0]["status"] == "satisfied" and out[0]["progress"] == 1.0
    # 10 turns old: no evidence needed
    out, warnings = apply_intent_ops(
        base, [{"op": "abandon", "id": "i1"}], 20, _no)
    assert out[0]["status"] == "abandoned" and warnings == []

def test_intent_block_lowers_progress_and_unknown_id_warns():
    base, _ = apply_intent_ops(
        [], [{"op": "add", "intent": "escape the city"},
             {"op": "progress", "id": "i1"},
             {"op": "progress", "id": "i1"}], 10, _ok)
    assert base[0]["progress"] == pytest.approx(0.4)
    out, _ = apply_intent_ops(base, [{"op": "block", "id": "i1"}], 11, _ok)
    assert out[0]["progress"] == pytest.approx(0.2)
    assert out[0]["last_progress_turn"] == 11
    _, warnings = apply_intent_ops(base, [{"op": "progress", "id": "i9"}], 11, _ok)
    assert any("i9" in w for w in warnings)

def test_intent_auto_dormant_after_thirty_turns():
    base, _ = apply_intent_ops(
        [], [{"op": "add", "intent": "escape the city"}], 0, _ok)
    out, warnings = apply_intent_ops(base, [], 40, _ok)
    assert out[0]["status"] == "dormant"
    assert any("dormant" in w for w in warnings)

# ---- Leak scan ----

def test_leak_scan_flags_suppressed_want_but_not_enacted():
    wants = [
        {"want": "leave this town tonight", "urgency": 0.9,
         "serves": "drive", "suppressed": True},
        {"want": "order another drink", "urgency": 0.5,
         "serves": "situational", "enacted": True},
    ]
    leaks = leak_scan(["I need to leave this town tonight."], wants, None, [])
    assert len(leaks) == 1 and "suppressed want" in leaks[0]
    # voicing the enacted want is deliberate action, not a leak
    assert leak_scan(["Another drink, please, and keep them coming."],
                     wants, None, []) == []

def test_leak_scan_flags_undercurrent():
    undercurrent = {"label": "anger", "v": -0.4, "a": 0.3,
                    "source": "the insult from the captain", "serves": "drive"}
    leaks = leak_scan(["I keep thinking about the insult from the captain."],
                      [], undercurrent, [])
    assert len(leaks) == 1 and "undercurrent" in leaks[0]

def test_leak_scan_flags_unenacted_intention_only():
    intentions = [{"id": "i3", "intent": "steal the ledger from the back room",
                   "status": "active"}]
    leaks = leak_scan(["Tonight I steal the ledger."], [], None, intentions)
    assert len(leaks) == 1 and "i3" in leaks[0]
    # an enacted want serving that intention makes speaking it deliberate
    wants = [{"want": "take the ledger", "urgency": 0.9,
              "serves": "i3", "enacted": True}]
    assert leak_scan(["Tonight I steal the ledger."], wants, None, intentions) == []

def test_leak_scan_is_total():
    assert leak_scan(None, None, None, None) == []
    assert leak_scan(["", None], [{}], {}, [{}]) == []

# ---- Tell gate ----

def test_tell_gate_threshold():
    assert not tell_gate({"subtlety": 0.9}, 0.3, 0.3, 0.2)
    assert tell_gate({"subtlety": 0.8}, 0.3, 0.3, 0.2)   # inclusive threshold
    # missing subtlety defaults to 0.5; missing observer terms to 0
    assert tell_gate({}, 0.5, 0.0, 0.0)
    assert not tell_gate({}, 0.4, 0.0, 0.0)
    assert tell_gate(None, 1.0, 0.0, 0.0)
    assert tell_gate({"subtlety": "loud"}, None, None, None) is False

# ---- Drive strain ----

def _drive_hit(impact, certainty, agency, why="his own oath got his brother killed"):
    return appraise([{"serves": "drive", "impact": impact,
                      "certainty": certainty, "agency": agency,
                      "why": why}], _priority_of)

def test_strain_confirmed_contradiction_accrues_more_when_self_caused():
    self_strain, self_entry = update_drive_strain(
        0.0, [], _drive_hit(-0.9, 0.9, "self"), "drive", None, 0)
    other_strain, other_entry = update_drive_strain(
        0.0, [], _drive_hit(-0.9, 0.9, "other",
                            why="the baron's men razed the farm"),
        "drive", None, 0)
    # 0.25 * 0.9 * 0.9, x1.5 for self-agency
    assert other_strain == pytest.approx(0.2025)
    assert self_strain == pytest.approx(0.30375)
    assert self_strain > other_strain
    assert self_entry["source"] == "contradiction"
    assert self_entry["why"] == "his own oath got his brother killed"
    assert self_entry["delta"] == pytest.approx(0.30375, abs=1e-3)
    assert set(self_entry) == {"source", "why", "delta"}  # caller stamps turn

def test_strain_below_floor_or_offdrive_contradiction_accrues_nothing():
    # Below the strain certainty floor (0.5): a near-guess doesn't accrue.
    strain, entry = update_drive_strain(
        0.3, [], _drive_hit(-0.9, 0.4, "self"), "drive", None, 0)
    assert strain == pytest.approx(0.3) and entry is None  # too uncertain
    offdrive = appraise([{"serves": "i1", "impact": -0.9, "certainty": 0.9,
                          "agency": "self", "why": "the plan failed"}],
                        _priority_of)
    strain, entry = update_drive_strain(0.3, [], offdrive, "drive", None, 0)
    assert strain == pytest.approx(0.3) and entry is None  # not the drive's wound


def test_strain_accrues_from_drive_wound_even_when_not_dominant():
    # Live root cause (Enterprise run, Vorne t14): the beat wounded an intention
    # (-0.6 @ 0.9 -> weight 0.43, dominant) AND the drive (-0.5 @ 0.8 self ->
    # weight 0.40). The old "dominant-only" rule discarded the drive wound
    # because the intention edged it out, so strain never built. The drive
    # wound must register whenever present.
    gi = [{"serves": "i1", "impact": -0.6, "certainty": 0.9, "agency": "self",
           "why": "the immediate task failed"},
          {"serves": "drive", "impact": -0.5, "certainty": 0.8, "agency": "self",
           "why": "his life's work was careless of the human price"}]
    ap = appraise(gi, _priority_of)
    assert ap["dominant"]["serves"] == "i1"          # intention is dominant...
    assert ap["drive_impact"]["serves"] == "drive"   # ...but the drive is surfaced
    strain, entry = update_drive_strain(0.0, [], ap, "", "", 0)
    assert strain > 0 and entry["source"] == "contradiction"  # accrues anyway


def test_strain_moderate_certainty_drive_contradiction_accrues():
    # The calibration fix: an authentic, less-than-certain drive wound
    # (certainty 0.7) DOES accrue -- a rupture is inherently uncertain, so
    # gating at 0.8 discarded exactly the signals that should build strain
    # (observed live: a capable model's -0.35 @ 0.7 accrued nothing).
    strain, entry = update_drive_strain(
        0.0, [], _drive_hit(-0.35, 0.7, "other"), "drive", None, 0)
    assert strain == pytest.approx(0.0612, abs=1e-3)  # 0.25 * 0.35 * 0.7
    assert entry["source"] == "contradiction"

def test_strain_relief_pays_down_and_clamps_at_zero():
    relief = _drive_hit(0.8, 1.0, "self", why="the oath held and saved her")
    strain, entry = update_drive_strain(0.5, [], relief, "drive", None, 0)
    assert strain == pytest.approx(0.26)       # -0.30 * 0.8 * 1.0
    assert entry["source"] == "relief"
    assert entry["delta"] == pytest.approx(-0.24, abs=1e-3)
    strain, _ = update_drive_strain(0.1, [], relief, "drive", None, 0)
    assert strain == 0.0

def test_strain_suppression_drift_only_when_choosing_against_drive():
    empty = appraise([], _priority_of)
    strain, entry = update_drive_strain(0.2, [], empty, "situational", "drive", 0)
    assert strain == pytest.approx(0.26)
    assert entry["source"] == "suppression"
    assert entry["delta"] == pytest.approx(0.06)
    # enacting the drive, or suppressing something else, drifts nothing
    assert update_drive_strain(0.2, [], empty, "drive", "drive", 0)[1] is None
    assert update_drive_strain(0.2, [], empty, "situational", "i1", 0)[1] is None
    assert update_drive_strain(0.2, [], empty, None, None, 0)[1] is None

def test_strain_anti_pump_damper_zeroes_restated_grievance():
    first_strain, entry = update_drive_strain(
        0.0, [], _drive_hit(-0.9, 0.9, "self"), "drive", None, 0)
    log = [dict(entry, turn=5)]
    # a superset restatement of the same wound: similarity 1.0, no accrual
    restated = _drive_hit(-0.9, 0.9, "self",
                          why="his own oath got his brother killed that night")
    strain, entry2 = update_drive_strain(
        first_strain, log, restated, "drive", None, 0)
    assert strain == pytest.approx(first_strain) and entry2 is None
    # a genuinely fresh wound still accrues
    fresh = _drive_hit(-0.9, 0.9, "self",
                       why="the family disowned him before the whole village")
    strain, entry3 = update_drive_strain(
        first_strain, log, fresh, "drive", None, 0)
    assert strain > first_strain
    assert entry3["source"] == "contradiction"

def test_strain_damper_exempts_suppression_and_relief():
    _, entry = update_drive_strain(
        0.0, [], _drive_hit(-0.9, 0.9, "self"), "drive", None, 0)
    log = [dict(entry, turn=5)]
    restated = _drive_hit(-0.9, 0.9, "self",
                          why="his own oath got his brother killed that night")
    # damped contradiction, but suppression drift still lands
    strain, entry2 = update_drive_strain(0.4, log, restated, "situational", "drive", 0)
    assert strain == pytest.approx(0.46)
    assert entry2["source"] == "suppression"
    # relief matching a logged why still pays down
    relief = _drive_hit(0.8, 1.0, "self")
    strain, entry3 = update_drive_strain(0.5, log, relief, "drive", None, 0)
    assert strain == pytest.approx(0.26)
    assert entry3["source"] == "relief"

def test_strain_decays_on_sixty_turn_half_life():
    assert update_drive_strain(0.8, [], None, None, None, 60)[0] == pytest.approx(0.4)
    assert update_drive_strain(0.8, [], None, None, None, 120)[0] == pytest.approx(0.2)
    assert update_drive_strain(0.8, [], None, None, None, 0)[0] == pytest.approx(0.8)

def test_strain_dual_accrual_applies_both_reports_larger():
    strain, entry = update_drive_strain(
        0.0, [], _drive_hit(-0.9, 0.9, "self"), "situational", "drive", 0)
    assert strain == pytest.approx(0.30375 + 0.06)  # both deltas applied
    assert entry["source"] == "contradiction"       # larger magnitude reported

def test_strain_is_total_on_junk():
    assert update_drive_strain(None, None, None, None, None, None) == (0.0, None)
    strain, entry = update_drive_strain(
        "hot", "not a log", {"dominant": "junk"}, 7, [], "soon")
    assert strain == 0.0 and entry is None

# ---- Drive rupture detection ----

def test_rupture_fires_only_when_both_keys_turn():
    hit = _drive_hit(-0.8, 0.9, "self")
    out = detect_drive_rupture(0.7, hit, 100, None)
    assert out is not None
    assert out["direction"] == "contradiction"
    assert out["why"] == "his own oath got his brother killed"
    assert out["score"] == pytest.approx(0.8 * 0.9 * 1.15, abs=1e-3)
    # high strain, ordinary beat: smolders without igniting
    assert detect_drive_rupture(0.95, _drive_hit(-0.4, 0.9, "self"), 100, None) is None
    assert detect_drive_rupture(0.95, appraise([], _priority_of), 100, None) is None
    # catastrophic beat, cold start: bounces off
    assert detect_drive_rupture(0.1, _drive_hit(-1.0, 1.0, "self"), 100, None) is None

def test_rupture_requires_confirmed_drive_scale_event():
    # Below the certainty floor (0.4), or not serving the drive: event_score 0.
    assert detect_drive_rupture(0.9, _drive_hit(-1.0, 0.4, "self"), 100, None) is None
    offdrive = appraise([{"serves": "i1", "impact": -1.0, "certainty": 1.0,
                          "agency": "self", "why": "the plan collapsed"}],
                        _priority_of)
    assert detect_drive_rupture(0.9, offdrive, 100, None) is None
    # The fix: a STRONG but not-certain (0.7) self-caused drive wound at high
    # strain now ignites -- the magnitude gate (event_score >= 0.55) keeps it
    # earned; only the certainty bar moved off the 0.8 that had made an honest
    # (uncertain) rupture impossible.
    out = detect_drive_rupture(0.9, _drive_hit(-1.0, 0.7, "self"), 100, None)
    assert out is not None and out["direction"] == "contradiction"

def test_rupture_self_agency_multiplier_tips_the_event_gate():
    # base 0.6 * 0.9 = 0.54 < 0.55; self-caused: 0.621 >= 0.55
    assert detect_drive_rupture(0.7, _drive_hit(-0.6, 0.9, "other"), 100, None) is None
    out = detect_drive_rupture(0.7, _drive_hit(-0.6, 0.9, "self"), 100, None)
    assert out is not None and out["score"] == pytest.approx(0.621, abs=1e-3)

def test_rupture_transformative_gain_fires_as_transformation():
    out = detect_drive_rupture(
        0.7, _drive_hit(0.9, 1.0, "other", why="she forgave him everything"),
        100, None)
    assert out is not None
    assert out["direction"] == "transformation"
    assert out["score"] == pytest.approx(0.9)

def test_rupture_cooldown_blocks_within_forty_turns():
    hit = _drive_hit(-1.0, 1.0, "self")
    assert detect_drive_rupture(0.9, hit, 50, 20) is None   # 30 turns since
    assert detect_drive_rupture(0.9, hit, 50, 10) is not None  # exactly 40
    assert detect_drive_rupture(0.9, hit, 50, None) is not None

def test_rupture_is_total_on_junk():
    assert detect_drive_rupture(None, None, None, None) is None
    assert detect_drive_rupture("high", {"dominant": "junk"}, "soon", "never") is None

# ---- Drive-shift validation ----

_OLD_DRIVE = {"essence": "protect the family at any cost",
              "expression": "shields kin before himself",
              "taboo": "never abandon kin"}
_RUPTURE = {"why": "his own oath to the family got his brother killed",
            "direction": "contradiction", "score": 0.83}

def test_validate_rejects_without_rupture_window():
    normalized, kind, warnings = validate_drive_shift(
        {"essence": "atone for what the oath cost his brother",
         "because": "his oath got his brother killed"},
        _OLD_DRIVE, [], None)
    assert normalized is None and kind == "none"
    assert any("rupture" in w for w in warnings)

def test_validate_rejects_junk_and_empty_essence():
    assert validate_drive_shift("junk", _OLD_DRIVE, [], _RUPTURE)[:2] == (None, "none")
    assert validate_drive_shift(None, _OLD_DRIVE, [], _RUPTURE)[:2] == (None, "none")
    normalized, kind, warnings = validate_drive_shift(
        {"essence": "   ", "because": "his oath got his brother killed"},
        _OLD_DRIVE, [], _RUPTURE)
    assert normalized is None and kind == "none"
    assert any("essence" in w for w in warnings)

def test_validate_rejects_missing_evidence():
    normalized, kind, warnings = validate_drive_shift(
        {"essence": "atone for what the oath cost his brother",
         "because": "the harvest festival is coming"},
        _OLD_DRIVE, [], _RUPTURE)
    assert normalized is None and kind == "none"
    assert any("relate" in w for w in warnings)

def test_validate_rejects_unrelated_essence_unless_a_former_drive_anchors_it():
    proposal = {"essence": "become the greatest baker in the city",
                "because": "his oath got his brother killed"}
    normalized, kind, warnings = validate_drive_shift(
        proposal, _OLD_DRIVE, [], _RUPTURE)
    assert normalized is None and kind == "none"
    assert any("unrelated" in w for w in warnings)
    # a former drive he once held makes the same essence coherent again
    former = [former_drive_entry(
        {"essence": "be the finest baker in the city"}, 12, "the fire")]
    normalized, kind, _ = validate_drive_shift(
        proposal, _OLD_DRIVE, former, _RUPTURE)
    assert kind == "break"
    assert normalized["essence"] == "become the greatest baker in the city"

def test_validate_downgrades_rephrase_to_bend():
    normalized, kind, warnings = validate_drive_shift(
        {"essence": "keep the family safe at any cost",
         "expression": "watches over them from a distance",
         "because": "his oath got his brother killed"},
        _OLD_DRIVE, [], _RUPTURE)
    assert kind == "bend"
    assert normalized["essence"] == _OLD_DRIVE["essence"]  # old essence kept
    assert normalized["expression"] == "watches over them from a distance"
    assert normalized["taboo"] == _OLD_DRIVE["taboo"]      # unchanged fields kept
    assert any("bend" in w for w in warnings)
    # the same rephrase with nothing else changed is no shift at all
    normalized, kind, warnings = validate_drive_shift(
        {"essence": "keep the family safe at any cost",
         "because": "his oath got his brother killed"},
        _OLD_DRIVE, [], _RUPTURE)
    assert normalized is None and kind == "none"
    assert any("rephrase" in w for w in warnings)

def test_validate_accepts_coherent_break_and_fills_from_old():
    normalized, kind, warnings = validate_drive_shift(
        {"essence": "atone for what the oath cost his brother",
         "expression": "serves the wronged quietly",
         "taboo": "never swear another oath",
         "because": "his oath got his brother killed"},
        _OLD_DRIVE, [], _RUPTURE)
    assert kind == "break" and warnings == []
    assert normalized == {"essence": "atone for what the oath cost his brother",
                          "expression": "serves the wronged quietly",
                          "taboo": "never swear another oath"}
    # omitted expression/taboo fall back to the old drive's
    normalized, kind, _ = validate_drive_shift(
        {"essence": "atone for what the oath cost his brother",
         "because": "his oath got his brother killed"},
        _OLD_DRIVE, [], _RUPTURE)
    assert kind == "break"
    assert normalized["expression"] == _OLD_DRIVE["expression"]
    assert normalized["taboo"] == _OLD_DRIVE["taboo"]

def test_former_drive_entry_builds_scar_and_is_total():
    scar = former_drive_entry(_OLD_DRIVE, 82, "his oath got his brother killed")
    assert scar == {"essence": "protect the family at any cost",
                    "expression": "shields kin before himself",
                    "taboo": "never abandon kin",
                    "ended_turn": 82,
                    "by_event": "his oath got his brother killed"}
    assert former_drive_entry(None, None, None) == {
        "essence": "", "expression": "", "taboo": "",
        "ended_turn": 0, "by_event": ""}

# ---- Serves normalization ----

_INTENTS = [
    {"id": "i1", "intent": "read the core log myself", "status": "active"},
    {"id": "i2", "intent": "keep Vale away from the array", "status": "active"},
]

def test_normalize_serves_passes_unprefixed_through():
    assert normalize_serves("drive", _INTENTS) == "drive"
    assert normalize_serves("i2", _INTENTS) == "i2"
    assert normalize_serves("situational", _INTENTS) == "situational"
    assert normalize_serves("  drive  ", _INTENTS) == "drive"

def test_normalize_serves_strips_prefix_to_bare_id():
    assert normalize_serves("intention:i1", _INTENTS) == "i1"
    assert normalize_serves("Intention: i2", _INTENTS) == "i2"

def test_normalize_serves_resolves_prefixed_text_to_id():
    # exact text
    assert normalize_serves(
        "intention:read the core log myself", _INTENTS) == "i1"
    # terse restatement (overlap-coefficient subset short-circuit)
    assert normalize_serves("intention:read the core log", _INTENTS) == "i1"
    assert normalize_serves(
        "intention:keep Vale away from the array", _INTENTS) == "i2"

def test_normalize_serves_unresolvable_returns_stripped_remainder():
    # an unmatched remainder falls to the caller's situational default
    out = normalize_serves("intention:conquer the galaxy", _INTENTS)
    assert out == "conquer the galaxy"
    assert _priority_of(out) == 0.4

def test_normalize_serves_is_total_on_junk():
    assert normalize_serves(None, _INTENTS) == ""
    assert normalize_serves("intention:", _INTENTS) == ""
    assert normalize_serves("intention:i1", None) == "i1"  # stripped, no crash
    assert normalize_serves(5, ["junk", None]) == "5"
    assert normalize_serves("intention:x", ["junk", {"id": None}]) == "x"
