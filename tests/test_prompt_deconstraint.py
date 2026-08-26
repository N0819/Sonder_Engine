"""The deconstraint pass: what left the Director's sheets, and what arrived.

Measured 2026-08-25 over the live corpus (2,723 resolved turns). Two sheets
were carrying scar tissue: `director_interpret` at 20,875 characters with 17
prohibitions to 5 invitations, `director_establish` at 15,790 with 25 to 2. An
unknown fraction of both was ALSO enforced in code, which makes those lines
pure token cost and pure discouragement -- a sheet that teaches a model to be
careful rather than good.

Every prohibition removed was removed because a deterministic guard already
held it. THE GUARD IS WHAT THIS FILE PINS: the sheet no longer says it, the
engine still does it. Every invitation added was added because the engine
READS the field on every beat and no sheet named it, so nothing the Director
could write would reach it.

No firewall clause was cut. The one that lived on a channel that moved
(`contact_assertions` -> the contact specialist's `contact_ops`) moved with it
and is pinned in `tests/test_player_contact_onset.py`.
"""

from __future__ import annotations

import inspect

import pytest

from llm.prompts import DEFAULT_PROMPTS, get_prompt, interpret_delegation_note
from llm.schemas import ActionElement, DirectorEstablish, RoomDef, SceneEntityDef


PACKS = ("en", "ja")


def _interpret(language="en"):
    return get_prompt("director_interpret", language)


def _establish(language="en"):
    return get_prompt("director_establish", language)


# --- prohibitions whose guard is unconditional -------------------------------

class TestTheEngineWritesItSoTheSheetStoppedAskingForIt:
    """Both channels are assigned unconditionally after the model answers, so
    whatever it wrote there was discarded on every beat of every story."""

    def test_authority_claims_are_extracted_not_requested(self):
        import agents.director as director

        source = inspect.getsource(director.director_interpret)
        assert 'fl["authority_claims"] = _extract_authority_claims(' in source
        for language in PACKS:
            assert "authority_claims" not in _interpret(language)

    def test_resolution_flags_are_computed_in_both_branches(self):
        import agents.director as director

        source = inspect.getsource(director.director_interpret)
        # Both branches assign, so there is no path on which a model-authored
        # value survives -- see agents.common._requires_reaction_phase, whose
        # own behaviour is pinned by tests/test_authored_outcome_attribution.py
        # and tests/test_world_model_action_stage.py.
        assert source.count('fl["resolution_flags"]["contested"]') == 2
        assert source.count('fl["resolution_flags"]["possible_reactors"]') == 2
        for language in PACKS:
            assert "resolution_flags" not in _interpret(language)

    def test_the_authored_outfit_is_restored_after_the_model_answers(self):
        import agents.director as director

        source = inspect.getsource(director.director_establish)
        assert "attire[entity] = entry" in source
        assert 'out["attire"] = attire' in source
        # What survives in the sheet is the fact, not the procedure.
        assert "initial_outfit is authoritative" in _establish()
        assert "copy its wearing and state into attire" not in _establish()

    def test_the_simulation_clock_is_seeded_not_asked_for(self):
        import agents.director as director

        source = inspect.getsource(director.director_establish)
        assert 'out.setdefault("simulation_clock"' in source
        for language in PACKS:
            assert "SIMULATION CLOCK" not in _establish(language)
            assert "シミュレーション時計をelapsed_seconds" not in _establish(language)

    def test_a_duplicated_cast_body_is_renamed_not_forbidden(self):
        import agents.director as director

        source = inspect.getsource(director.director_establish)
        assert "reconcile_cast_entity_names(out, ctx.cast" in source
        assert "never duplicated here" not in _establish()


class TestThePassOneInstructionThatItsOwnSuffixVoided:
    """`interpret_delegation_note` is appended unconditionally at
    agents/director.py:595 -- the fan-out is the only Director path, so there
    is no beat on which the monolithic reading is the live one. The sheet
    spent 3,583 characters teaching a decomposition that the next 1,575
    characters declared void."""

    def test_the_note_is_still_the_thing_that_assigns_the_channels(self):
        note = interpret_delegation_note()
        assert "SPECIALISTS ENCODE, YOU DECOMPOSE" in note
        assert "contact_assertions empty" in note
        # It no longer overrides an instruction that is gone.
        assert "OVERRIDES the PASS 1 instruction" not in note

    def test_the_sheet_no_longer_enumerates_the_delegated_channels(self):
        prompt = _interpret()
        assert "the FULL state_diff structure director_resolve uses" not in prompt
        assert "the same channels, the same shapes, no subset" not in prompt
        # The authority statement and the one rule no guard holds both stay.
        assert "You are not a lesser authority than director_resolve" in prompt
        assert "The one thing that is NOT an assertion is an unfinished attempt" \
            in prompt

    def test_the_contact_grammar_lives_on_the_hand_that_writes_contacts(self):
        assert "DIRECT FELT CONTACT" not in _interpret()
        assert "crossed_target_part" not in _interpret()
        # ...and is intact where the beat's contact_ops are actually authored.
        assert "crossed_target_part" in DEFAULT_PROMPTS["director_contact"]


# --- invitations: fields the engine reads that no sheet named ---------------

class TestACapabilityNobodyIsToldAboutIsACapabilityNobodyHas:

    @pytest.mark.parametrize("field", [
        "phase", "phase_id", "depends_on", "participants",
        "requires_contacts", "referents",
    ])
    def test_the_compound_declaration_fields_are_offered(self, field):
        assert field in ActionElement.model_fields, field
        for language in PACKS:
            assert field in _interpret(language), (field, language)

    def test_arrives_is_in_the_contract_line_not_only_the_body(self):
        """The field defaults TRUE and the guard fires only on FALSE, so a
        model reading the closing output shape as the contract silently
        disabled the whole approach-vs-arrival mechanism the paragraph above
        it exists to feed."""
        for language in PACKS:
            prompt = _interpret(language)
            shape = prompt[prompt.index("movement:null|{"):]
            assert "arrives:true|false" in shape[:120], language

    def test_scheduled_assertions_are_in_the_flow_shape(self):
        for language in PACKS:
            assert '"scheduled_assertions"' in _interpret(language), language

    @pytest.mark.parametrize("field,model", [
        ("crowd_ops", DirectorEstablish),
        ("contact_action_ops", DirectorEstablish),
        ("weather", DirectorEstablish),
        ("exposure", RoomDef),
        ("light", RoomDef),
        ("light_source", SceneEntityDef),
        ("enclosure", SceneEntityDef),
        ("ubiquitous", SceneEntityDef),
    ])
    def test_the_establish_contract_line_names_what_the_schema_reads(
            self, field, model):
        assert field in model.model_fields, field
        for language in PACKS:
            assert field in _establish(language), (field, language)


# --- house rule 3: a declared-and-unreferenced field is worse than no field --

class TestTheFieldsWithNoReaderAreGone:
    """Each had ZERO readers in the tree. `mode` was the pointed one: its
    comment promised that player-authored NPC interiority is "rerouted to that
    character's own agent as an offer rather than enacted as truth", nothing
    implemented the reroute, and the interpret sheet enforced the discard in
    the same breath. A promise living in a comment is not a capability."""

    @pytest.mark.parametrize("field", ["mode", "instruments", "duration"])
    def test_action_element_declares_no_unread_field(self, field):
        assert field not in ActionElement.model_fields, field

    def test_establish_declares_no_opening(self):
        """`DirectorEstablish.opening` had no reader anywhere, and asking for
        it contradicted the sheet's own first sentence ("you do not write
        prose that reaches the player")."""
        assert "opening" not in DirectorEstablish.model_fields
        for language in PACKS:
            assert "opening:''" not in _establish(language), language
