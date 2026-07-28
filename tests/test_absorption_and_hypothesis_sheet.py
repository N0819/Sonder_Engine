"""Sensation constrains cognition, and the mind holds a bounded, explicit sheet.

Two ideas, one mechanism. `psychology_runtime.cognitive_absorption` measures how
much of a mind its own body is currently claiming -- deliberately blind to
valence, because intense pleasure occupies attention exactly as intense pain
does. `theory_of_mind` then spends that figure three ways: the effortful end of
the confidence-cap gradient erodes, forming a NEW hypothesis gets a floor to
clear, and the stable hypothesis sheet holds fewer open questions.
"""

from __future__ import annotations

import pytest

from psychology_runtime import cognitive_absorption
from theory_of_mind import (
    absorbed_cap,
    apply_mind_model_updates,
    due_for_reappraisal,
    formation_floor,
    hypothesis_key,
    select_active_hypotheses,
    sheet_capacity,
)


def _claim(about, claim, kind="goal", confidence=0.6):
    return {"about_entity": about, "claim": claim, "kind": kind,
            "confidence": confidence}


# ---- absorption -----------------------------------------------------------

def test_absorption_is_blind_to_valence():
    """The point of the metric: pain and pleasure are opposites in what they
    are worth and identical in what they cost."""
    assert cognitive_absorption({"pain": 0.8}) == cognitive_absorption(
        {"pleasure": 0.8})


def test_mild_sensation_is_cheap_and_severe_sensation_is_not():
    """Convex on purpose -- an earlier concave curve read pain 0.2 as nearly
    half the mind gone, which would cripple characters with ordinary
    discomfort."""
    assert cognitive_absorption({"pain": 0.2}) < 0.2
    assert cognitive_absorption({"pain": 0.8}) > 0.7


def test_saturated_drive_absorbs_without_being_distress():
    """A demanding drive is not a coping failure -- load/overloaded stay
    strain-only -- but it is still something the mind is busy with."""
    assert cognitive_absorption({"pleasure": 0.3, "saturated": True}) >= 0.45


def test_absorption_does_not_read_strain_as_its_signal(monkeypatch):
    """Reading `strain` would say a body at the ceiling of a powerful pleasant
    stimulus is perfectly free to theorise."""
    pleasant = {"pleasure": 0.95, "charge": 0.9}
    assert cognitive_absorption(pleasant, {"strain": 0.0}) > 0.8


# ---- the effort gradient --------------------------------------------------

def test_noticing_survives_what_mentalising_does_not():
    """Easterbrook narrowing: a character in agony does not get worse at
    seeing what is in front of them, only at modelling why."""
    assert absorbed_cap("observation", 1.0) == absorbed_cap("observation", 0.0)
    assert absorbed_cap("second_order", 1.0) < absorbed_cap("second_order", 0.0) * 0.5
    assert absorbed_cap("goal", 1.0) < absorbed_cap("goal", 0.0)


# ---- formation ------------------------------------------------------------

def test_forming_a_new_belief_is_what_absorption_blocks():
    """Reinforcing a belief you hold is nearly free; starting a theory about
    someone is the expensive operation."""
    assert formation_floor(0.0) == 0.0
    assert formation_floor(1.0) > 0.5

    blocked = apply_mind_model_updates(
        {}, [_claim("Vorne", "wants to leave", confidence=0.4)], 1,
        absorption=0.9)
    assert "Vorne" not in (blocked.get("mind_models") or {})


def test_an_existing_belief_still_reinforces_under_absorption():
    """Recognising more of what you already think is AUTOMATIC processing and
    survives absorption; building a theory is CONTROLLED and does not
    (Shiffrin & Schneider). Applying the eroded cap to both made a beat that
    CONFIRMED a settled belief cut it from 0.6 to 0.37 -- absorption eating
    convictions it should only have stopped the character adding to."""
    state = apply_mind_model_updates({}, [_claim("Vorne", "wants to leave")], 1)
    before = state["mind_models"]["Vorne"]["hypotheses"][0]["confidence"]
    state = apply_mind_model_updates(
        state, [_claim("Vorne", "wants to leave", confidence=0.9)], 2,
        absorption=0.95)
    after = state["mind_models"]["Vorne"]["hypotheses"][0]["confidence"]
    assert after > before


def test_absorption_is_not_itself_evidence_against_a_belief():
    """Disconfirming evidence legitimately weakens a belief -- that is the
    plasticity blend, and absorption must not add to it. Being in pain is not
    an argument against what you already think, so the same evidence has to
    land identically whether the character is calm or absorbed."""
    def _after(absorption):
        state = apply_mind_model_updates(
            {}, [_claim("Vorne", "wants to leave")], 1)
        state = apply_mind_model_updates(
            state, [_claim("Vorne", "wants to leave", confidence=0.05)], 1,
            absorption=absorption)
        return state["mind_models"]["Vorne"]["hypotheses"][0]["confidence"]

    assert _after(1.0) == pytest.approx(_after(0.0))


def test_a_belief_formed_under_absorption_is_stamped_not_just_capped():
    state = apply_mind_model_updates(
        {}, [_claim("Vorne", "is about to run", kind="stated_fact",
                    confidence=0.85)], 3, absorption=0.8)
    hyp = state["mind_models"]["Vorne"]["hypotheses"][0]
    assert hyp["formed_under"]["absorption"] == pytest.approx(0.8, abs=1e-3)


def test_a_calm_belief_carries_no_stamp():
    state = apply_mind_model_updates({}, [_claim("Vorne", "wants to leave")], 1)
    assert "formed_under" not in state["mind_models"]["Vorne"]["hypotheses"][0]


# ---- reappraisal ----------------------------------------------------------

def test_a_belief_reached_in_agony_comes_back_up_when_calm():
    """Neither standing as though it were reached calmly, nor discounted
    forever -- reviewed once there is room to review it."""
    hyp = {"formed_under": {"absorption": 0.9, "turn": 3}}
    assert due_for_reappraisal(hyp, 0.05)
    assert not due_for_reappraisal(hyp, 0.85)


def test_a_calm_belief_is_never_flagged_for_reappraisal():
    assert not due_for_reappraisal({"claim": "x"}, 0.0)


# ---- the sheet ------------------------------------------------------------

def _busy_models():
    state = {}
    for i, (about, claim, conf) in enumerate([
        ("Vorne", "is hiding something", 0.9),
        ("Vorne", "wants the letter", 0.8),
        ("Mara", "is frightened", 0.7),
        ("Mara", "blames me", 0.6),
        ("Doc", "is lying", 0.55),
        ("Doc", "knows the way out", 0.5),
    ]):
        state = apply_mind_model_updates(
            state, [_claim(about, claim, confidence=conf)], 1)
    return state["mind_models"]


def test_the_sheet_is_bounded_and_ranked():
    entries, keys = select_active_hypotheses(_busy_models(), [], 3, 1)
    assert len(entries) == 3 == len(keys)
    confidences = [e["confidence"] for e in entries]
    assert confidences == sorted(confidences, reverse=True)


def test_every_entry_is_marked_as_conjecture():
    """A mind reading its own guesses back as settled fact is the same
    information-layer collapse this engine polices between minds, happening
    inside one. The field name carries the epistemic status."""
    entries, _ = select_active_hypotheses(_busy_models(), [], 5, 1)
    assert entries
    for entry in entries:
        assert "i_suspect" in entry
        assert "claim" not in entry


def test_absorption_shrinks_the_sheet():
    assert sheet_capacity(0.0) == 5
    assert sheet_capacity(1.0) == 1
    assert sheet_capacity(0.5) < sheet_capacity(0.0)
    models = _busy_models()
    calm, _ = select_active_hypotheses(models, [], sheet_capacity(0.0), 1)
    hurt, _ = select_active_hypotheses(models, [], sheet_capacity(0.95), 1)
    assert len(hurt) < len(calm)


def test_the_sheet_is_stable_under_small_wobbles():
    """Without hysteresis the sheet churns every turn as confidences wobble,
    and stops being 'what I am actively wondering about'."""
    models = _busy_models()
    _entries, keys = select_active_hypotheses(models, [], 2, 1)
    incumbent = keys[-1]
    # A challenger just barely stronger than the weakest incumbent.
    challenger = hypothesis_key("Doc", "goal", "is lying")
    assert challenger not in keys
    _again, keys_again = select_active_hypotheses(models, keys, 2, 1)
    assert incumbent in keys_again, "incumbent lost its slot to a marginal rival"


def test_a_clearly_stronger_challenger_does_take_the_slot():
    """Stability is hysteresis, not a lock."""
    models = _busy_models()
    _e, keys = select_active_hypotheses(models, [], 2, 1)
    state = apply_mind_model_updates(
        {"mind_models": models},
        [_claim("Doc", "is about to kill me", kind="observation",
                confidence=1.0)], 2)
    _e2, keys2 = select_active_hypotheses(state["mind_models"], keys, 2, 2)
    assert hypothesis_key("Doc", "observation", "is about to kill me") in keys2


def test_an_empty_mind_yields_an_empty_sheet():
    assert select_active_hypotheses({}, [], 5, 1) == ([], [])
    assert select_active_hypotheses(None, None, 0, 1) == ([], [])


# ---- reappraisal actually does something ----------------------------------

class TestReappraisalIsNotJustALabel:
    """`formed_under` was stamped, mentioned in the payload, and acted on by
    nothing -- the entire re-evaluation rested on the model choosing to comply
    with an advisory string, which is not a guarantee this engine accepts
    anywhere else. Reappraisal now raises plasticity, so a belief reached in
    extremity genuinely moves further on the same evidence once the character
    is clear-headed."""

    def _formed_in_agony(self):
        return apply_mind_model_updates(
            {}, [_claim("Vorne", "means to betray us", confidence=0.6)], 1,
            absorption=0.9)

    def test_a_revisited_belief_moves_further_than_a_calm_one(self):
        revisited = apply_mind_model_updates(
            self._formed_in_agony(),
            [_claim("Vorne", "means to betray us", confidence=0.1)], 2,
            absorption=0.0)
        control = apply_mind_model_updates(
            apply_mind_model_updates(
                {}, [_claim("Vorne", "means to betray us", confidence=0.6)], 1),
            [_claim("Vorne", "means to betray us", confidence=0.1)], 2)
        assert (revisited["mind_models"]["Vorne"]["hypotheses"][0]["confidence"]
                < control["mind_models"]["Vorne"]["hypotheses"][0]["confidence"])

    def test_revisiting_clears_the_stamp(self):
        """Otherwise it is re-flagged on every calm beat forever."""
        after = apply_mind_model_updates(
            self._formed_in_agony(),
            [_claim("Vorne", "means to betray us", confidence=0.1)], 2,
            absorption=0.0)
        hyp = after["mind_models"]["Vorne"]["hypotheses"][0]
        assert "formed_under" not in hyp
        assert hyp["reappraised_turn"] == 2

    def test_no_boost_while_still_absorbed(self):
        """The point is the clear head, not the passage of time."""
        still_hurting = apply_mind_model_updates(
            self._formed_in_agony(),
            [_claim("Vorne", "means to betray us", confidence=0.1)], 2,
            absorption=0.9)
        assert "formed_under" in (
            still_hurting["mind_models"]["Vorne"]["hypotheses"][0])

    def test_the_sheet_flag_respects_current_state(self):
        """Hardcoding current absorption to 0.0 -- as this did -- told a
        character still in the grip of the thing to reconsider it 'now that
        the body does not have your attention', while it plainly did."""
        models = self._formed_in_agony()["mind_models"]
        calm, _ = select_active_hypotheses(models, [], 5, 2, absorption=0.0)
        hurt, _ = select_active_hypotheses(models, [], 5, 2, absorption=0.9)
        assert "reappraisal" in calm[0]
        assert "reappraisal" not in hurt[0]


# ---- F8: the declared kind is not taken on trust --------------------------

class TestDeclaredKindIsNotTrusted:
    """Every ceiling keys off a `kind` the model declares. Nothing checked it,
    so a model could buy confidence by mislabelling a trait inference as an
    observation -- and the absorption erosion built on that gradient stopped
    applying with it."""

    @pytest.mark.parametrize("claim,expected", [
        ("Vorne is the sort of person who sells people out", "trait"),
        ("Vorne wants the letter", "goal"),
        ("Vorne thinks I know about the shipment", "second_order"),
        ("Vorne always takes the back stairs", "trait"),
        ("Vorne is really the harbourmaster's son", "identity"),
    ])
    def test_a_mislabelled_claim_is_re_kinded_down(self, claim, expected):
        from theory_of_mind import effective_kind
        assert effective_kind("observation", claim) == expected

    def test_a_genuine_observation_keeps_its_ceiling(self):
        from theory_of_mind import effective_kind
        assert effective_kind(
            "observation", "Vorne is standing by the door") == "observation"

    def test_inference_can_only_ever_lower_the_ceiling(self):
        """The safety property. This is text matching, and text matching is not
        something to build an information boundary on -- but this is confidence
        calibration, not a boundary, and it is arranged so a misfire makes a
        character less sure, never more."""
        from theory_of_mind import _TOM_CONFIDENCE_CAPS, effective_kind
        claims = [
            "Vorne is standing by the door", "Vorne wants the letter",
            "Vorne always lies", "Vorne told me he would come",
            "Vorne thinks I know", "something with no cue at all",
        ]
        for declared in _TOM_CONFIDENCE_CAPS:
            for claim in claims:
                got = effective_kind(declared, claim)
                assert (_TOM_CONFIDENCE_CAPS[got]
                        <= _TOM_CONFIDENCE_CAPS[declared]), (declared, claim)

    def test_the_re_kind_is_enforced_end_to_end(self):
        """A mislabelled claim must actually be capped and stored under the
        corrected kind -- capping under one kind and merging under another was
        already called out as an inconsistent ceiling in this module."""
        state = apply_mind_model_updates(
            {}, [{"about_entity": "Vorne", "kind": "observation",
                  "claim": "Vorne is the sort of person who sells people out",
                  "confidence": 1.0}], 1)
        hyp = state["mind_models"]["Vorne"]["hypotheses"][0]
        assert hyp["kind"] == "trait"
        assert hyp["confidence"] <= 0.45

    def test_both_entry_points_agree(self):
        from theory_of_mind import cap_mind_model_updates
        raw = [{"about_entity": "Vorne", "kind": "observation",
                "claim": "Vorne wants the letter", "confidence": 1.0}]
        capped = cap_mind_model_updates(raw)
        assert capped[0]["kind"] == "goal"
        state = apply_mind_model_updates({}, capped, 1)
        assert state["mind_models"]["Vorne"]["hypotheses"][0]["kind"] == "goal"


def test_reinforcement_preserves_belief_provenance():
    """`merged` is rebuilt from the incoming update, so first_seen_turn and
    formed_under were dropped on every reinforcement -- a belief reached in
    agony and merely restated became one that had always been held calmly.
    Provenance belongs to the belief, not to the update that last touched it."""
    state = apply_mind_model_updates(
        {}, [_claim("Vorne", "means to betray us", confidence=0.6)], 1,
        absorption=0.9)
    for turn in (2, 3, 4):
        state = apply_mind_model_updates(
            state, [_claim("Vorne", "means to betray us", confidence=0.7)],
            turn, absorption=0.9)
    hyp = state["mind_models"]["Vorne"]["hypotheses"][0]
    assert hyp["formed_under"]["turn"] == 1
    assert hyp["first_seen_turn"] == 1


class TestPlaceClaimsDoNotCompete:
    """Hypotheses group by (about_entity, kind) and explain each other away
    within a group. That is right for a mind -- rival theories about one person
    genuinely should suppress each other -- and exactly backwards for space.

    Found live: a character mapping a maze filed every room under one umbrella
    entity ("maze layout in this sector"), so learning about one chamber
    actively suppressed what it knew about another. Two independent facts
    treated as rival explanations of one subject, and the map dismantled itself
    as fast as it was built.
    """

    ROOMS = ["Chamber 0505", "Chamber 0805", "Private Bedroom"]

    def _rekey(self, updates, protected=()):
        from theory_of_mind import rekey_place_claims
        return rekey_place_claims(updates, self.ROOMS, protected=protected)

    def test_two_rooms_become_two_entities(self):
        got = self._rekey([
            {"about_entity": "maze layout", "claim": "Chamber 0505 has a bench"},
            {"about_entity": "maze layout", "claim": "Chamber 0805 has slate"},
        ])
        assert [u["about_entity"] for u in got] == ["Chamber 0505", "Chamber 0805"]

    def test_a_claim_about_a_person_stays_with_the_person(self):
        """Even when it says where they were standing."""
        got = self._rekey(
            [{"about_entity": "Vorne",
              "claim": "was standing in Chamber 0505 and looked afraid"}],
            protected=["Vorne"])
        assert got[0]["about_entity"] == "Vorne"

    def test_an_ambiguous_two_room_claim_is_left_alone(self):
        """Guessing would scatter the belief onto the wrong room."""
        got = self._rekey([{"about_entity": "maze layout",
                            "claim": "Chamber 0505 connects to Chamber 0805"}])
        assert got[0]["about_entity"] == "maze layout"

    def test_a_claim_naming_no_room_is_left_alone(self):
        got = self._rekey([{"about_entity": "maze layout",
                            "claim": "the air is colder here"}])
        assert got[0]["about_entity"] == "maze layout"

    def test_longer_room_names_are_not_shadowed(self):
        from theory_of_mind import rekey_place_claims
        got = rekey_place_claims(
            [{"about_entity": "x", "claim": "Chamber 0505 is lit"}],
            ["Chamber 05", "Chamber 0505"])
        assert got[0]["about_entity"] == "Chamber 0505"

    def test_different_rooms_no_longer_suppress_each_other(self):
        """The property that matters: independent rooms keep independent
        confidence."""
        from theory_of_mind import apply_mind_model_updates
        raw = [
            {"about_entity": "maze layout", "kind": "observation",
             "claim": "Chamber 0505 has a toppled bench", "confidence": 0.7},
            {"about_entity": "maze layout", "kind": "observation",
             "claim": "Chamber 0805 has grey slate", "confidence": 0.7},
        ]
        collided = apply_mind_model_updates({}, list(raw), 1)
        hyps = collided["mind_models"]["maze layout"]["hypotheses"]
        suppressed = min(h["confidence"] for h in hyps)

        split = apply_mind_model_updates({}, self._rekey(raw), 1)
        assert set(split["mind_models"]) == {"Chamber 0505", "Chamber 0805"}
        kept = min(m["hypotheses"][0]["confidence"]
                   for m in split["mind_models"].values())
        assert kept > suppressed

    def test_the_same_room_still_revises(self):
        """Belief change over time must survive: a later claim about the SAME
        place still competes with the earlier one."""
        from theory_of_mind import apply_mind_model_updates
        state = apply_mind_model_updates({}, self._rekey(
            [{"about_entity": "maze layout", "kind": "observation",
              "claim": "Chamber 0505 has a toppled bench", "confidence": 0.8}]), 1)
        state = apply_mind_model_updates(state, self._rekey(
            [{"about_entity": "maze layout", "kind": "observation",
              "claim": "Chamber 0505 is empty and swept", "confidence": 0.9}]), 2)
        hyps = state["mind_models"]["Chamber 0505"]["hypotheses"]
        assert len(hyps) == 2, "a competing claim about the same room must persist"
        bench = next(h for h in hyps if "bench" in h["claim"])
        assert bench["confidence"] < 0.8, "the displaced claim should be explained away"


class TestSubjectIsNotEvidenceOfSameness:
    """What a claim is ABOUT is carried by about_entity; only what it SAYS
    should decide whether two claims are the same belief.

    Naming the subject inside the claim is ordinary phrasing, but it inflated
    every same-subject pair toward a match -- so two distinct facts about one
    room (or one person) merged and the later silently overwrote the earlier.
    Surfaced by per-room keying, which puts the room name in every claim about
    it, but it was always true of people.
    """

    def test_two_facts_about_one_room_are_not_the_same_belief(self):
        from theory_of_mind import claim_similarity, _SIMILARITY_THRESHOLD
        a = "Chamber 0505 has a toppled bench"
        b = "Chamber 0505 is empty and swept"
        assert claim_similarity(a, b) >= _SIMILARITY_THRESHOLD, "the old behaviour"
        assert claim_similarity(a, b, ignore="Chamber 0505") < _SIMILARITY_THRESHOLD

    def test_two_facts_about_one_person_are_not_the_same_belief(self):
        from theory_of_mind import claim_similarity, _SIMILARITY_THRESHOLD
        a, b = "Vorne is afraid of the dark", "Vorne wants to leave the city"
        assert claim_similarity(a, b, ignore="Vorne") < _SIMILARITY_THRESHOLD

    def test_a_genuine_restatement_still_matches(self):
        """The point is not to stop matching -- reinforcement must survive."""
        from theory_of_mind import claim_similarity, _SIMILARITY_THRESHOLD
        assert claim_similarity(
            "Vorne is hiding something",
            "Vorne seems to be hiding something about the letter",
            ignore="Vorne") >= _SIMILARITY_THRESHOLD

    def test_dropping_the_subject_never_empties_a_claim(self):
        """A claim that is ONLY its subject must still compare, not divide by
        zero."""
        from theory_of_mind import claim_similarity
        assert claim_similarity("Vorne", "Vorne", ignore="Vorne") == 1.0
