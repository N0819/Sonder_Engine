"""Two records the narrator was written from, and no check scoring against them.

SPEECH MARKING. `DIALOGUE FIDELITY` asks only whether the WORDS survived:
`_contains_quote` strips markup before comparing -- deliberately, so a tag
inside a quote does not read as a dropped line -- and then substring-searches.
An emphasised span with no quotation marks passes it whole. Measured: view
`Mara says in a quiet voice: "We should not be here."` against prose
`She looks away. <i>We should not be here.</i>` raised no warning at all. A
delivered line is SPEECH and the page marks speech with quotation marks; the
same words outside every quoted region are a different speech act, which is
why the reader's own contract reserves emphasis for a thought the prose is
voicing rather than quoting.

EXPOSURE. `_check_narrator_fidelity` took event order, positions, room names
and portal states -- and nothing about dress. The ledger's coverage answer has
existed as an engine vocabulary the whole time (`covered_regions` over
`REGIONS`), and nothing consumed it, so a region the ledger still had covered
could be narrated bare with no upstream stage having asserted it: on an
ordinary beat the composer suppresses standing state already delivered, so
the body's dress is simply absent from the page the narrator writes from.

Both are warnings, not enforceable prefixes. Promotion costs a whole narrator
call per firing and is a measurement, not an edit.
"""

from __future__ import annotations

import json

import pytest

from agents.common import (_check_attire_fidelity, _check_narrator_fidelity,
                           _check_speech_marking, attire_exposure_facts,
                           exposure_owner_refs)


VIEW = 'Mara says in a quiet voice: "We should not be here."'


class TestSpeechIsMarkedAsSpeech:
    def test_a_delivered_line_rendered_unquoted_is_reported(self):
        warnings = _check_speech_marking(
            "She looks away. <i>We should not be here.</i>",
            ["We should not be here."])
        assert warnings
        assert warnings[0].startswith(
            "Delivered line rendered without quotation marks")

    def test_the_same_line_inside_quotes_is_fine(self):
        assert not _check_speech_marking(
            'She looks away. "We should not be here."',
            ["We should not be here."])

    def test_markup_inside_the_quotes_is_still_fine(self):
        """The strip exists so a tag inside a quote does not read as a
        dropped line; it must not start reading as an unmarked one either."""
        assert not _check_speech_marking(
            'She looks away. "We should <i>not</i> be here."',
            ["We should not be here."])

    def test_a_line_that_never_reached_the_page_is_not_this_checks_business(
            self):
        """A dropped line is the fidelity check's finding. Reporting it twice
        would buy two rewrites for one failure."""
        assert not _check_speech_marking(
            "She looks away and says nothing.", ["We should not be here."])

    def test_the_players_own_lines_are_excluded(self):
        """PLAYER ECHO RULE requires their ABSENCE, so their marking is a
        different rule's business and scoring them here would push the model
        to break one rule to satisfy the other."""
        assert not _check_speech_marking(
            "You had said it already: we should not be here.",
            ["We should not be here."],
            excluded_bodies={"we should not be here"})

    def test_typographic_quotes_count_as_marking(self):
        assert not _check_speech_marking(
            "She looks away. “We should not be here.”",
            ["We should not be here."])

    def test_a_short_line_is_seen(self):
        """Regions rather than a quote regex: `_QUOTE_BODY_RE` needs four
        characters between the marks, so a short line is invisible to it."""
        assert _check_speech_marking("She shakes her head. <i>No.</i>", ["No."])

    def test_it_reaches_the_screen(self):
        warnings = _check_narrator_fidelity(
            {"prose": "She looks away. <i>We should not be here.</i>"}, VIEW)
        assert any(w.startswith("Delivered line rendered without")
                   for w in warnings)

    def test_it_is_not_enforceable(self):
        """Promotion costs a whole narrator call per firing, and its
        false-positive rate is unmeasured."""
        from language_runtime import english_linguistic

        prefixes = english_linguistic(
            "agents.narration", "_ENFORCEABLE_PREFIXES")
        assert not any(
            p.startswith("Delivered line rendered without") for p in prefixes)


def _covered_scene(region="torso", garment="linen shirt"):
    return {"attire": {"Mara": {"regions": {region: {"garments": [
        {"name": garment, "kind": "shirt", "state": "worn",
         "coverage": region}]}}}}}


class TestTheLedgerDecidesWhatIsBare:
    FACTS = [{"refs": ["her", "Mara's"], "covered": ["torso"]}]

    def test_prose_calling_a_covered_region_bare_is_reported(self):
        warnings = _check_attire_fidelity(
            "Her bare torso caught the light.", self.FACTS)
        assert warnings
        assert "attire ledger" in warnings[0]

    def test_prose_agreeing_with_the_ledger_is_not(self):
        assert not _check_attire_fidelity(
            "Her linen shirt caught the light.", self.FACTS)

    def test_scenery_is_never_a_body(self):
        """The exposure word must be bound to the region noun by an
        OWNERSHIP token of that body."""
        assert not _check_attire_fidelity(
            "The bare boards creaked. A torso-high crate stood by the wall.",
            self.FACTS)

    def test_a_speakers_claim_is_not_narration(self):
        assert not _check_attire_fidelity(
            '"Your bare torso will freeze out there," she said.', self.FACTS)

    def test_the_unarmed_idiom_is_not_an_undressed_one(self):
        """"With your bare hands" is an English statement about being
        unarmed that names a REGION by accident."""
        assert not _check_attire_fidelity(
            "She pried it open with her bare hands.",
            [{"refs": ["her"], "covered": ["hands"]}])

    def test_a_region_the_ledger_does_not_cover_is_free(self):
        assert not _check_attire_fidelity(
            "Her bare arms were scratched.", self.FACTS)

    def test_one_warning_per_body(self):
        """A rewrite is bought once; enumerating every region would spend the
        same call several times over."""
        warnings = _check_attire_fidelity(
            "Her bare torso and bare legs caught the light.",
            [{"refs": ["her"], "covered": ["torso", "legs"]}])
        assert len(warnings) == 1


class TestWhichBodiesTheFactsCover:
    def test_a_covered_region_becomes_a_fact(self):
        facts = attire_exposure_facts(_covered_scene(), [("Mara", ["her"])])
        assert facts == [{"refs": ["her"], "covered": ["torso"]}]

    def test_a_partially_exposed_region_is_left_out(self):
        """A garment worn open still counts as concealing, so prose calling
        that region bare is defensible and a warning would spend a rewrite on
        a true sentence."""
        scene = _covered_scene()
        scene["attire"]["Mara"]["regions"]["torso"]["garments"][0][
            "covered_zones"] = {"torso": ["chest"]}
        facts = attire_exposure_facts(scene, [("Mara", ["her"])])
        assert facts == []

    def test_a_body_with_no_ledger_entry_contributes_nothing(self):
        assert attire_exposure_facts(_covered_scene(),
                                     [("Absent", ["their"])]) == []

    def test_a_body_with_no_ownership_token_contributes_nothing(self):
        """Without a word that would own the region in prose there is nothing
        to bind an exposure claim to, and an unbound claim is scenery."""
        assert attire_exposure_facts(_covered_scene(), [("Mara", [])]) == []

    def test_the_caller_decides_who_is_in_it(self):
        """No perception opinion lives here -- the same division
        `_position_delta_payload` keeps for rooms."""
        scene = _covered_scene()
        scene["attire"]["Unseen"] = scene["attire"]["Mara"]
        facts = attire_exposure_facts(scene, [("Mara", ["her"])])
        assert len(facts) == 1


class TestWhoOwnsARegionInProse:
    def test_the_narration_person_decides_the_players_possessive(self):
        """Not the persona's pronouns: a second-person narration says "your"
        about the player whatever their sheet says."""
        refs = exposure_owner_refs("second", "Kestrel", {"possessive": "her"})
        assert "your" in refs

    def test_a_named_body_is_owned_by_its_display_and_its_pronoun(self):
        refs = exposure_owner_refs(None, "Mara", {"possessive": "her"})
        assert "Mara's" in refs and "her" in refs

    def test_an_unknown_person_yields_no_person_token(self):
        assert exposure_owner_refs("third", "", None) == []


class TestTheScreenGainedTheInput:
    def test_the_check_runs_from_the_screen(self):
        warnings = _check_narrator_fidelity(
            {"prose": "Her bare torso caught the light."}, "",
            attire_facts=[{"refs": ["her"], "covered": ["torso"]}])
        assert any("attire ledger" in w for w in warnings)

    def test_a_caller_passing_no_attire_facts_is_unchanged(self):
        assert not any(
            "attire ledger" in w for w in _check_narrator_fidelity(
                {"prose": "Her bare torso caught the light."}, ""))

    def test_it_is_not_enforceable(self):
        from language_runtime import english_linguistic

        prefixes = english_linguistic(
            "agents.narration", "_ENFORCEABLE_PREFIXES")
        assert not any(p.startswith("Narrated exposure contradicts")
                       for p in prefixes)

    def test_the_narrator_builds_the_facts_behind_the_perception_gate(self):
        """A check fact is not a payload field, but the bodies it covers are
        still exactly the ones perception admitted."""
        import inspect

        from agents import narration

        source = inspect.getsource(narration.narrator)
        assert "attire_exposure_facts" in source
        assert "pos_facts" in source


class TestTheVocabularyIsLanguageData:
    @pytest.mark.parametrize("lang", ["en", "ja"])
    def test_both_packs_carry_the_exposure_shape(self, lang):
        card = json.load(open(f"language_packs/{lang}/cards/linguistics.json",
                              encoding="utf-8"))
        shape = card["agents.common"]["_EXPOSURE_STATE"]
        assert set(shape) == {"state", "assertion", "idiom",
                              "person_possessive"}
        assert set(shape["person_possessive"]) == {"first", "second", "third"}
