"""The drive ceiling: what physical contact does and does not permit.

Measured live (chat 95, 2026-08-29): a character sat at `pleasure 1.0,
charge 1.0, saturated: true` off a contact ledger holding four SETTLED
records -- a hand gripping a hip, weight pressing. The only gate on
`somatic_impact.pleasure` was that its `why` was a non-empty string, so any
sentence licensed any magnitude, and at her cadence the integral's
equilibrium was 3.25 against a clamp of 1.0: welded to the ceiling by beat
four with no path down.

The rule these pin: being touched and being overwhelmed are different
states. No contact of any kind reaches `_CHARGE_SATURATION`; the last
stretch is climbed, in beats, by continued active stimulation.
"""
from mind import psychology_runtime as psych
from world import stimulation as stim
from world import spatial


def _hedonic(tier, intensity, beats, *, active=None, floor=0.0, prev=None):
    active = tier >= stim.TIER_ACTIVE if active is None else active
    state = prev if isinstance(prev, dict) else {}
    for _ in range(beats):
        state = psych.resolve_hedonic(
            state,
            {"somatic_impact": {"pleasure": intensity, "why": "contact"}},
            {"pleasure_sensitivity": 0.5}, {}, 1.0,
            stimulation={"tier": tier, "active": active,
                         "intensity_floor": floor, "regions": []})
    return state


class TestNoContactCanOverwhelm:
    """Every rung a contact can reach sits below saturation, and the model
    claiming the maximum does not change that -- it is the whole point."""

    def test_words_and_sight_cap_low(self):
        assert _hedonic(stim.TIER_NONE, 1.0, 40)["charge"] == 0.30

    def test_through_clothing_caps_higher_and_still_short(self):
        assert _hedonic(stim.TIER_INDIRECT, 1.0, 40)["charge"] == 0.55

    def test_skin_held_still_does_not_saturate(self):
        """The measured case: a hand on a hip, weight pressing, nothing
        moving. Real contact, real arousal, not overwhelm."""
        held = _hedonic(stim.TIER_DIRECT, 1.0, 40)
        assert held["charge"] == 0.75
        assert held["saturated"] is False
        assert held["charge"] < psych._CHARGE_SATURATION


class TestOverwhelmIsEarnedInBeats:
    def test_relentless_and_intense_saturates_in_two(self):
        assert _hedonic(stim.TIER_ACTIVE, 1.0, 1)["saturated"] is False
        assert _hedonic(stim.TIER_ACTIVE, 1.0, 2)["saturated"] is True

    def test_firm_and_steady_takes_longer(self):
        assert _hedonic(stim.TIER_ACTIVE, 0.6, 2)["saturated"] is False
        assert _hedonic(stim.TIER_ACTIVE, 0.6, 5)["saturated"] is True

    def test_teasing_builds_far_more_slowly_at_the_same_tier(self):
        """SAME RUNG, different speed. Teasing builds slowly because it keeps
        stopping, and `motion` says so without anything reading a word."""
        state, teased = {}, []
        for beat in range(20):
            moving = beat % 2 == 0
            state = psych.resolve_hedonic(
                state,
                {"somatic_impact": {"pleasure": 0.3, "why": "teasing"}},
                {"pleasure_sensitivity": 0.5}, {}, 1.0,
                stimulation={
                    "tier": stim.TIER_ACTIVE if moving else stim.TIER_DIRECT,
                    "active": moving, "intensity_floor": 0.0, "regions": []})
            teased.append(state["charge"])
        assert not any(c >= psych._CHARGE_SATURATION for c in teased)
        assert teased[-1] > 0.75          # it IS building, past the held rung
        assert _hedonic(stim.TIER_ACTIVE, 1.0, 20)["charge"] > teased[-1]

    def test_intensity_cannot_buy_reach_only_speed(self):
        """The appraisal's magnitude is safe to trust here precisely because
        it moves a body faster through a range the contact already earned,
        and cannot grant a range it did not."""
        for intensity in (0.1, 0.5, 1.0):
            assert _hedonic(stim.TIER_DIRECT, intensity, 40)["charge"] <= 0.75


class TestArousalFadesRatherThanSwitchingOff:
    def test_a_dropped_ceiling_never_undercuts_ordinary_decay(self):
        saturated = _hedonic(stim.TIER_ACTIVE, 1.0, 6)
        assert saturated["saturated"] is True
        after = psych.resolve_hedonic(
            saturated, {}, {}, {}, 1.0,
            stimulation={"tier": stim.TIER_NONE, "active": False,
                         "intensity_floor": 0.0, "regions": []})
        assert after["charge"] > 0.9
        later = psych.resolve_hedonic(
            saturated, {}, {}, {}, 12.0,
            stimulation={"tier": stim.TIER_NONE, "active": False,
                         "intensity_floor": 0.0, "regions": []})
        assert abs(later["charge"] - saturated["charge"] * 0.5) < 0.01

    def test_release_still_zeroes_everything(self):
        saturated = _hedonic(stim.TIER_ACTIVE, 1.0, 6)
        done = psych.resolve_hedonic(
            saturated, {}, {}, {}, 1.0, released=True,
            stimulation={"tier": stim.TIER_ACTIVE, "active": True,
                         "intensity_floor": 0.0, "regions": []})
        assert done["charge"] == 0.0
        assert done["stim_climb"] == 0.0
        assert done["stim_continuity"] == 0.0


class TestTheCeilingIsInertWithoutAScene:
    """Charter bodies, tools and every caller with no scene pass no
    stimulation at all, and must behave exactly as before the ceilings."""

    def test_omitting_stimulation_restores_the_old_curve(self):
        state = {}
        for _ in range(20):
            state = psych.resolve_hedonic(
                state, {"somatic_impact": {"pleasure": 1.0, "why": "c"}},
                {"pleasure_sensitivity": 0.5}, {}, 1.0)
        assert state["charge"] == 1.0
        assert "stim_tier" not in state


class TestTheRungIsReadFromTheLedger:
    """No vocabulary anywhere: the rung comes from `motion`, `relation`, the
    contacted part and the clothing over it."""

    @staticmethod
    def _scene(part, motion, worn=(), regions=None):
        return {
            "positions": {"Mira": "room", "Corin": "room"},
            "entities": {},
            "attire": {"Mira": {"wearing": list(worn),
                                "regions": regions or {}}},
            "contacts": [{
                "actor": "Corin", "actor_part": "hand",
                "target": "Mira", "target_part": part,
                "manner": "grip", "relation": "surface", "motion": motion,
            }],
        }

    def test_a_held_hand_on_a_responsive_region_is_not_active(self):
        got = stim.stimulation_of(self._scene("groin", "settled"), "Mira")
        assert got["tier"] == stim.TIER_DIRECT
        assert got["active"] is False

    def test_the_same_hand_moving_is(self):
        got = stim.stimulation_of(self._scene("groin", "moving"), "Mira")
        assert got["tier"] == stim.TIER_ACTIVE
        assert got["active"] is True

    def test_a_garment_between_drops_it_a_rung(self):
        scene = self._scene(
            "groin", "moving", worn=["silk panties"],
            regions={"groin": {"garments": [
                {"name": "silk panties", "state": "worn"}]}})
        assert stim.stimulation_of(scene, "Mira")["tier"] == stim.TIER_INDIRECT

    def test_a_non_responsive_region_is_contact_and_no_more(self):
        assert stim.stimulation_of(
            self._scene("hip", "moving"), "Mira")["tier"] == stim.TIER_INDIRECT

    def test_a_card_says_which_regions_answer(self):
        """No hardcoded anatomy: a body that answers somewhere the default
        does not says so on its own sheet, and the engine's default is one
        region rather than a list of them."""
        scene = self._scene("waist", "moving")
        assert stim.stimulation_of(scene, "Mira")["tier"] == stim.TIER_INDIRECT
        assert stim.stimulation_of(
            scene, "Mira",
            {"responsive_regions": ["waist"]})["tier"] == stim.TIER_ACTIVE

    def test_a_part_outside_the_region_vocabulary_is_plain_contact(self):
        """THE KNOWN LIMIT, pinned rather than hidden. `attire.REGIONS` is
        the vocabulary coverage is expressed in, and it is what a contact
        part is supposed to use ("contacts, injury, position and facing
        continue to use REGIONS"). Live data drifts -- chat 95 carries `hip`,
        `back`, `body` -- and such a part reads as contact and no more. It
        cannot be bridged with a part-name synonym table: AGENTS.md forbids
        one twice, because `tail_spade` is a nameable place on a tail rather
        than `tail` blurred. See docs/UNBUILT.md."""
        assert stim.stimulation_of(
            self._scene("hip", "moving"), "Mira",
            {"responsive_regions": ["waist"]})["tier"] == stim.TIER_INDIRECT

    def test_touching_someone_else_does_not_stimulate_the_toucher(self):
        """One record per pair. Read from both ends, a character could
        overwhelm herself by putting a hand on somebody."""
        got = stim.stimulation_of(self._scene("groin", "moving"), "Corin")
        assert got["active"] is False

    def test_furniture_is_comfort_not_drive(self):
        scene = self._scene("groin", "moving")
        scene["contacts"][0]["actor"] = "wide_bed"
        scene["entities"]["wide_bed"] = {"name": "wide bed", "kind": "object"}
        assert stim.stimulation_of(scene, "Mira")["tier"] == stim.TIER_NONE


class TestInsideIsNotTheSameQuestionAsSensitive:
    """`relation: interior` says nothing is between two surfaces. That settles
    the CLOTHING question and only that one -- it does not say the site
    answers to being touched.

    Reading it as though it did made every cavity equivalent: a body swallowed
    into a stomach, a finger in a mouth and a body taken into a vulva would
    all have saturated the same. The ledger's own words for those are
    "stomach", "mouth" and "vagina" -- chat 95 t45 carries the last two
    verbatim in `target_interior` -- and telling them apart by name is the
    body-part table this module refuses. Which site answers is a fact about
    that body, so the body says."""

    @staticmethod
    def _scene(target_part, interior, motion="moving"):
        return {"positions": {"Mira": "room", "Corin": "room"},
                "entities": {}, "attire": {"Mira": {"wearing": []}},
                "contacts": [{"actor": "Corin", "actor_part": "body",
                              "target": "Mira", "target_part": target_part,
                              "target_interior": interior, "manner": "push",
                              "relation": "interior", "motion": motion}]}

    RESPONSIVE = {"responsive_regions": ["vagina", "clit"]}

    def test_a_body_swallowed_into_a_stomach_is_contact_and_no_more(self):
        assert stim.stimulation_of(
            self._scene("stomach lining", "stomach"),
            "Mira", self.RESPONSIVE)["tier"] == stim.TIER_INDIRECT

    def test_a_mouth_is_contact_and_no_more(self):
        assert stim.stimulation_of(
            self._scene("tongue", "mouth"),
            "Mira", self.RESPONSIVE)["tier"] == stim.TIER_INDIRECT

    def test_a_site_the_body_answers_to_is_direct(self):
        got = stim.stimulation_of(
            self._scene("inner walls", "vagina"), "Mira", self.RESPONSIVE)
        assert got["tier"] == stim.TIER_ACTIVE
        assert got["intensity_floor"] > 0

    def test_the_enclosing_passage_is_read_as_well_as_the_endpoint(self):
        """`inner walls` is not a name the responsive set is likely to carry;
        `vagina` is what the ledger puts in `target_interior`, and it is the
        surface doing the receiving."""
        assert stim.stimulation_of(
            self._scene("inner walls", "vagina"),
            "Mira", {"responsive_regions": ["vagina"]})["tier"] == \
            stim.TIER_ACTIVE

    def test_interior_skips_the_wardrobe_and_nothing_else(self):
        """A dressed body still counts an interior contact on a responsive
        site: there is nothing between two surfaces that are inside one
        another."""
        scene = self._scene("inner walls", "vagina")
        scene["attire"]["Mira"] = {"wearing": ["gown"], "regions": {
            "groin": {"garments": [{"name": "gown", "state": "worn"}]}}}
        assert stim.stimulation_of(
            scene, "Mira", self.RESPONSIVE)["tier"] == stim.TIER_ACTIVE

    def test_settled_is_direct_but_not_active(self):
        got = stim.stimulation_of(
            self._scene("inner walls", "vagina", motion="settled"),
            "Mira", self.RESPONSIVE)
        assert got["tier"] == stim.TIER_DIRECT
        assert got["active"] is False


class TestACardMayNameAPartTheRegionsCannot:
    def test_an_authored_part_counts_on_a_bare_body(self):
        scene = {"positions": {"Mira": "room", "Corin": "room"},
                 "entities": {}, "attire": {"Mira": {"wearing": []}},
                 "contacts": [{"actor": "Corin", "actor_part": "hand",
                               "target": "Mira", "target_part": "tail spade",
                               "manner": "stroke", "relation": "surface",
                               "motion": "moving"}]}
        assert stim.stimulation_of(scene, "Mira")["tier"] == stim.TIER_INDIRECT
        assert stim.stimulation_of(
            scene, "Mira",
            {"responsive_regions": ["tail spade"]})["tier"] == stim.TIER_ACTIVE

    def test_a_dressed_body_falls_back_to_contact_for_an_unplaceable_part(self):
        """Nothing can say whether a garment covers a region the clothing
        ledger has no name for, so a dressed body keeps the lower rung."""
        scene = {"positions": {"Mira": "room", "Corin": "room"},
                 "entities": {},
                 "attire": {"Mira": {"wearing": ["cloak"], "regions": {
                     "torso": {"garments": [{"name": "cloak",
                                             "state": "worn"}]}}}},
                 "contacts": [{"actor": "Corin", "actor_part": "hand",
                               "target": "Mira", "target_part": "tail spade",
                               "manner": "stroke", "relation": "surface",
                               "motion": "moving"}]}
        assert stim.stimulation_of(
            scene, "Mira",
            {"responsive_regions": ["tail spade"]})["tier"] == stim.TIER_INDIRECT


class TestTheHandThatNamedThePartsSaysWhetherItAnswers:
    """Nothing deterministic can tell a stomach from a vulva. Both are
    `relation: interior`, the ledger's words for them are "stomach" and
    "vagina", and matching those is the body-part synonym table
    `spatial_contacts.canonical_region` refuses -- which would be wrong for
    every body that is not human anyway.

    So the contact specialist judges it, where the anatomy is known, and says
    so on the contact. The engine reads it for one thing: how far that body's
    own arousal may build. It is never rendered and reaches no other mind."""

    @staticmethod
    def _scene(interior, erogenous=None):
        contact = {"actor": "Corin", "actor_part": "body", "target": "Mira",
                   "target_part": "lining", "target_interior": interior,
                   "manner": "push", "relation": "interior",
                   "motion": "moving"}
        if erogenous is not None:
            contact["erogenous"] = erogenous
        return {"positions": {"Mira": "room", "Corin": "room"},
                "entities": {}, "attire": {"Mira": {"wearing": []}},
                "contacts": [contact]}

    def test_a_site_it_marks_answers_however_it_is_spelled(self):
        assert stim.stimulation_of(
            self._scene("vagina", True), "Mira")["tier"] == stim.TIER_ACTIVE

    def test_a_site_it_does_not_mark_stays_contact(self):
        assert stim.stimulation_of(
            self._scene("stomach", False), "Mira")["tier"] == \
            stim.TIER_INDIRECT

    def test_silence_is_not_consent_to_saturate(self):
        assert stim.stimulation_of(
            self._scene("stomach"), "Mira")["tier"] == stim.TIER_INDIRECT

    def test_the_card_still_wins_where_it_speaks(self):
        """Either saying yes is yes: an author who wants the answer fixed for
        a body can fix it, without waiting on a judgment per beat."""
        assert stim.stimulation_of(
            self._scene("vagina"), "Mira",
            {"responsive_regions": ["vagina"]})["tier"] == stim.TIER_ACTIVE

    def test_the_flag_is_not_part_of_a_contacts_identity(self):
        """It describes the site, not which contact this is -- so re-judging
        it must not fork the record or orphan its actions."""
        from world import spatial
        scene = spatial.normalize_scene_contacts(self._scene("vagina", True))
        first = scene["contacts"][0]["contact_id"]
        scene = spatial.apply_contact_ops(scene, [
            {"op": "add", "actor": "Corin", "actor_part": "body",
             "target": "Mira", "target_part": "lining",
             "target_interior": "vagina", "manner": "push",
             "relation": "interior", "motion": "moving", "erogenous": False}],
            report=[])
        assert len(scene["contacts"]) == 1
        assert scene["contacts"][0]["contact_id"] == first
