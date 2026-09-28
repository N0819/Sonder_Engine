"""The offscreen specialist is retired; its channels went home.

Measured on the Harrowmere replay (2026-09-03): the world-traffic hand ran
on 1 of 40 turns. Its channels split three ways -- crowd, courier and
telling ops and the hearsay verdict to the social hand (speech and roster
consequences; charter SIMULATES crowds and couriers, the ops raise and send
them); the reactive-plan channel to the character's own result, because the
Director does not own psychology. Nothing named `offscreen` remains as a
hand, a role, a schema or a card.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TRAFFIC = ("crowd_ops", "courier_ops", "telling_ops",
           "ratified_claims", "contradicted_claims")


def test_the_hand_is_gone_from_every_registry():
    from agents.director import SPECIALISTS
    from llm.prompts import DEFAULT_PROMPTS, _prompt_card
    from llm.providers import ROLES
    from llm.schemas import SCHEMA_MAP, SPECIALIST_CHANNELS

    assert "offscreen" not in SPECIALISTS
    for language in ("en", "ja"):
        card = _prompt_card(language)
        assert "offscreen" not in card["specialists"], language
        assert not [key for key in card["encoder"] if "offscreen" in key], language
    assert "director_offscreen" not in ROLES
    assert "director_offscreen" not in SCHEMA_MAP
    assert "director_offscreen" not in SPECIALIST_CHANNELS
    assert "director_offscreen" not in DEFAULT_PROMPTS
    for language in ("en", "ja"):
        assert not (ROOT / "language_packs" / language / "cards" / "system_prompts"
                    / "specialists" / "offscreen").exists()


def test_the_social_hand_owns_the_traffic_in_all_three_registries():
    """The owners table, the owner's schema, and the pack: the social owner's
    order and the encoder's card, in both packs."""
    from agents.director import SPECIALISTS
    from llm.prompts import _prompt_card
    from llm.schemas import SPECIALIST_CHANNELS

    for channel in TRAFFIC:
        assert channel in SPECIALISTS["social"]["channels"]
        assert channel in SPECIALIST_CHANNELS["director_social"]
        for language in ("en", "ja"):
            card = _prompt_card(language)
            assert channel in card["specialists"]["social"]["order"], language
            assert channel in card["encoder"], language


def test_the_reactive_plan_channel_left_the_directors_diff():
    from llm import schemas
    from llm.schemas import StateDiff, _fields

    assert "offscreen_plan_ops" not in _fields(StateDiff)
    assert "offscreen_plan_ops" not in _fields(schemas.DirectorSocialSpecialist)
    assert not hasattr(schemas, "OffscreenPlanOp")
    assert not hasattr(schemas, "DirectorOffscreenSpecialist")


def test_the_gate_facts_no_longer_read_the_planning_floor(temp_db):
    from agents import director_scopes
    import inspect
    src = inspect.getsource(director_scopes)
    assert "offscreen_planning_enabled" not in src
    assert "offscreen_plan_ops" not in src
