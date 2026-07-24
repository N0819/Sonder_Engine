"""Regression tests for the deterministic pronoun-fidelity floor (W6 / P1).

`cast_pronouns` + the PRONOUN CONSISTENCY prompt rule (alpha3.1) reduced but
did not eliminate mid-scene pronoun flips -- a he/him character still picked
up a "her" in the confirmation run. `_check_pronoun_fidelity` is the
deterministic floor: it raises an ENFORCEABLE narrator warning, which drives
the existing correction-retry.

Its whole value depends on never crying wolf, so most of these tests pin the
cases it must stay silent on.
"""

import json

from agents.common import _check_narrator_fidelity, _check_pronoun_fidelity
from agents.narration import _ENFORCEABLE_PREFIXES, _cast_pronouns

HE = {"subject": "he", "object": "him", "possessive": "his"}
SHE = {"subject": "she", "object": "her", "possessive": "her"}
THEY = {"subject": "they", "object": "them", "possessive": "their"}


def test_flags_possessive_flip_on_named_subject():
    warnings = _check_pronoun_fidelity(
        "Vorne tightened her jaw and said nothing.", {"Vorne": HE})
    assert len(warnings) == 1
    assert "Vorne" in warnings[0] and "her" in warnings[0]


def test_flagged_warning_is_enforceable():
    """The warning must drive the narrator's correction-retry, not just sit in
    the step inspector -- that is the entire point of the deterministic floor."""
    warnings = _check_pronoun_fidelity(
        "Vorne straightened her shoulders.", {"Vorne": HE})
    assert warnings and warnings[0].startswith(_ENFORCEABLE_PREFIXES)


def test_flags_subject_flip_for_a_they_them_character():
    warnings = _check_pronoun_fidelity(
        "Alex studied the console. Alex knew he was being watched.",
        {"Alex": THEY})
    assert len(warnings) == 1
    assert "Alex" in warnings[0]


def test_surname_alone_still_identifies_the_character():
    warnings = _check_pronoun_fidelity(
        "Vorne raised her hand.", {"Kel Vorne": HE})
    assert len(warnings) == 1


def test_correct_pronouns_pass_clean():
    assert _check_pronoun_fidelity(
        "Vorne tightened his jaw. Vorne said nothing, and his hands stayed still.",
        {"Vorne": HE}) == []


def test_plural_they_about_a_gendered_character_is_not_a_flip():
    """"Vorne watched them scatter" is a group, not a pronoun flip -- singular
    they is far too common in ordinary prose to enforce against."""
    assert _check_pronoun_fidelity(
        "Vorne watched them scatter across the bridge.", {"Vorne": HE}) == []


def test_second_name_in_the_clause_makes_the_referent_ambiguous():
    assert _check_pronoun_fidelity(
        "Vorne handed Crusher her tricorder.",
        {"Vorne": HE, "Crusher": SHE}) == []


def test_pronoun_in_a_later_clause_is_not_scored():
    """The referent of "her" is the ensign, not Vorne. Only same-clause
    pronouns are scored."""
    assert _check_pronoun_fidelity(
        "Vorne glanced at the ensign; her hands were shaking.", {"Vorne": HE}) == []


def test_pronoun_inside_quoted_dialogue_is_exempt():
    """A speaker's "her" is about whoever they mean -- usually someone the
    clause never names."""
    assert _check_pronoun_fidelity(
        'Vorne shook his head. "I told her to stay off the bridge."',
        {"Vorne": HE}) == []
    assert _check_pronoun_fidelity(
        "Vorne shook his head. “I told her to stay off the bridge.”",
        {"Vorne": HE}) == []


def test_character_without_declared_pronouns_is_skipped():
    assert _check_pronoun_fidelity("Vorne raised her hand.", {"Vorne": {}}) == []


def test_mixed_or_neopronoun_sets_are_skipped():
    """Nothing outside the three closed paradigms is guessed at."""
    assert _check_pronoun_fidelity(
        "Vorne raised her hand.",
        {"Vorne": {"subject": "she", "object": "them", "possessive": "their"}}) == []
    assert _check_pronoun_fidelity(
        "Vorne raised her hand.",
        {"Vorne": {"subject": "xe", "object": "xem", "possessive": "xyr"}}) == []


def test_name_shared_by_two_cast_members_is_dropped():
    assert _check_pronoun_fidelity(
        "Vorne raised her hand.",
        {"Kel Vorne": HE, "Ria Vorne": SHE}) == []


def test_name_that_is_an_ordinary_word_is_not_scored():
    assert _check_pronoun_fidelity(
        "Will you hand him the padd?", {"Will": SHE}) == []


def test_repeated_flip_for_one_character_reports_once_per_pronoun():
    warnings = _check_pronoun_fidelity(
        "Vorne raised her hand. Vorne lowered her hand.", {"Vorne": HE})
    assert len(warnings) == 1


def test_empty_inputs_are_noops():
    assert _check_pronoun_fidelity("", {"Vorne": HE}) == []
    assert _check_pronoun_fidelity("Vorne raised her hand.", None) == []
    assert _check_pronoun_fidelity("Vorne raised her hand.", {}) == []


def test_narrator_fidelity_surfaces_the_mismatch():
    """Wired through the check the narrator stage actually calls."""
    warnings = _check_narrator_fidelity(
        {"prose": "Vorne tightened her jaw."},
        view="Vorne stands at the console.",
        cast_pronouns={"Vorne": HE})
    assert any(w.startswith("Pronoun mismatch for") for w in warnings)


def test_narrator_fidelity_without_cast_pronouns_is_unchanged():
    assert _check_narrator_fidelity(
        {"prose": "Vorne tightened her jaw."},
        view="Vorne stands at the console.") == []


def test_character_payload_pronouns_are_recognition_gated():
    """A speaker gets the pronouns of people they KNOW (so they stop guessing
    from a name), and nothing about a stranger in the room -- you don't know an
    unfamiliar person's pronouns."""
    from agents.character import _known_pronouns

    cast = [
        {"sheet": '{"identity": {"name": "Vorne", "pronouns": '
                  '{"subject": "he", "object": "him", "possessive": "his"}}}'},
        {"sheet": '{"identity": {"name": "Stranger", "pronouns": '
                  '{"subject": "she", "object": "her", "possessive": "her"}}}'},
        {"sheet": '{"identity": {"name": "Crusher", "pronouns": '
                  '{"subject": "she", "object": "her", "possessive": "her"}}}'},
    ]
    persona = {"identity": {"name": "Picard", "pronouns": HE}}

    known = _known_pronouns(cast, persona, {"Vorne", "Picard"},
                            exclude=["Crusher"])
    assert known == {"Vorne": HE, "Picard": HE}


def test_character_payload_pronouns_exclude_the_speaker():
    from agents.character import _known_pronouns

    cast = [{"sheet": '{"identity": {"name": "Vorne", "pronouns": '
                      '{"subject": "he", "object": "him", "possessive": "his"}}}'}]
    assert _known_pronouns(cast, None, {"Vorne"}, exclude=["Vorne"]) == {}


def test_perception_pronouns_skip_a_disguised_character(monkeypatch):
    """Canonical pronouns are part of the identity a disguise conceals -- handing
    them to the perception layer would out the subject in an unaware observer's
    view."""
    from agents import perception as perception_mod

    cast = [
        {"sheet": '{"identity": {"name": "Vorne", "pronouns": '
                  '{"subject": "he", "object": "him", "possessive": "his"}}}'},
        {"sheet": '{"identity": {"name": "Crusher", "pronouns": '
                  '{"subject": "she", "object": "her", "possessive": "her"}}}'},
    ]
    monkeypatch.setattr(perception_mod, "sheet_state",
                        lambda row: (json.loads(row["sheet"]), {}, {}))

    monkeypatch.setattr(perception_mod, "active_disguises", lambda cid: {})
    assert perception_mod._observed_pronouns(1, cast) == {"Vorne": HE, "Crusher": SHE}

    monkeypatch.setattr(perception_mod, "active_disguises",
                        lambda cid: {"vorne": {"description": "a Ferengi trader"}})
    assert perception_mod._observed_pronouns(1, cast) == {"Crusher": SHE}


def test_cast_pronouns_builder_reads_sheets():
    cast = [
        {"sheet": '{"identity": {"name": "Vorne", "pronouns": '
                  '{"subject": "he", "object": "him", "possessive": "his"}}}'},
        {"sheet": '{"identity": {"name": "Nameless"}}'},
        {"sheet": "not json"},
    ]
    assert _cast_pronouns(cast) == {"Vorne": HE}
    assert _cast_pronouns([]) == {}
    assert _cast_pronouns(None) == {}
