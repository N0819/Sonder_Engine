"""MASTER-038 (the surviving fragment): near-miss `stage` spellings must not
cost a repair model call.

`ActionElement.stage` is a real contract -- `_REACTIVE_STAGES` feeds
`_requires_reaction_phase`, which sets the contested flag that inserts
`reaction_loop` into the plan -- so the field stays, and no stage-keyed
constraint on resolver effects is added here (four such heuristics were
measured against a 1249-turn corpus and rejected; see
`agents/director_movement.py`'s approach-guard notes and `MovementDecl.arrives`).
What was broken is smaller: a model writing the unambiguous synonym
`initiation` raised a pydantic ValidationError and bought a whole extra
repair call for a value whose meaning was never in doubt.
"""

from __future__ import annotations

import pytest

from llm.schemas import ActionElement, ActionStage, normalize_action_stage


@pytest.mark.parametrize("spelling, meant", [
    ("initiation", ActionStage.preparation),
    ("setup", ActionStage.preparation),
    ("ongoing", ActionStage.sustained),
])
def test_known_synonyms_validate_without_repair(spelling, meant):
    assert ActionElement(stage=spelling).stage == meant


def test_case_and_whitespace_fold():
    assert ActionElement(stage=" Approach ").stage == ActionStage.approach
    assert ActionElement(stage="IMMEDIATE").stage == ActionStage.immediate


def test_real_members_are_untouched():
    for member in ActionStage:
        assert ActionElement(stage=member.value).stage == member


def test_an_alien_value_is_still_refused():
    """The alias map is deliberately small: anything that is not an
    unambiguous synonym must keep failing validation, so the repair path
    still sees genuinely alien answers rather than a silent guess."""
    with pytest.raises(Exception):
        ActionElement(stage="warpspeed")
    # And the normalizer passes it through UNTOUCHED, so the validation
    # error names what the model actually said.
    assert normalize_action_stage("warpspeed") == "warpspeed"
    assert normalize_action_stage(None) is None


def test_the_default_still_stands():
    assert ActionElement().stage == ActionStage.immediate
