"""`character_card_warnings` answers any card it is handed, raw or normalized.

Ten surfaces ask it, and they hand it two shapes. Nine pass a NORMALIZED card;
`confirm_promotion` passes the RAW body sheet, and there a scalar where a
section belongs -- `"psychology": "brave"`, `"embodiment": {"visible":
"tall"}` -- raised `AttributeError` on `.get` AFTER the promotion had written
the character, so the host saw a 500 for a promotion that succeeded and a
retry was refused as a name collision (story_scene_schema audit F12b).

The rule now: the SEMANTIC questions (a drive, goals, capacity, what the
summary names) are asked of the normalized card, which has one shape whatever
arrived; the STRUCTURAL questions (a station with no name, more stations than
are built, clothing at a region nothing declares) are asked of the card AS
WRITTEN, because normalization is exactly what repairs them away -- on a
normalized card those three can never fire (F12a; which card each route
passes is the routes' own business).
"""

from __future__ import annotations

import pytest

from story.character_schema import (INTERIOR_STATIONS_MAX,
                                    character_card_warnings,
                                    normalize_character_data)


@pytest.mark.parametrize("sheet", [
    {"psychology": "brave"},
    {"psychology": {"drive": "to keep her brother alive"}},
    {"psychology": {"drive": {"essence": 3}}},
    {"embodiment": {"visible": "tall"}},
    {"embodiment": "a tall woman"},
    {"initial_state": "restless"},
    {"simulation": "on"},
    {"initial_outfit": "a red coat"},
    "not a card",
    None,
])
def test_a_scalar_where_a_section_belongs_is_read_not_raised(sheet):
    warnings = character_card_warnings(sheet)
    assert isinstance(warnings, list)
    assert all(isinstance(w, str) for w in warnings)


def test_the_structural_warnings_answer_on_the_raw_card():
    raw = {"identity": {"name": "Kit"}, "embodiment": {"interior": [
        {"name": "the throat"}, {"description": "no name here"},
        *({"name": "station %d" % n} for n in range(INTERIOR_STATIONS_MAX)),
    ]}, "initial_outfit": {"regions": {"elbow": ["a silk band"]}}}
    text = " ".join(character_card_warnings(raw))
    assert "no name" in text
    assert "only the first" in text
    assert "elbow" in text


def test_a_raw_card_and_its_normalization_agree_on_the_semantics():
    raw = {"identity": {"name": "Kit"}}
    raw_text = " ".join(character_card_warnings(raw))
    normalized_text = " ".join(character_card_warnings(
        normalize_character_data(raw)))
    for phrase in ("No drive was authored", "No standing goals",
                   "No attentional capacity"):
        assert phrase in raw_text
        assert phrase in normalized_text


def test_a_textual_flag_is_still_reported_on_the_raw_card():
    text = " ".join(character_card_warnings(
        {"identity": {"name": "Kit"},
         "simulation": {"offscreen_agent": "yes"}}))
    assert "offscreen_agent" in text
