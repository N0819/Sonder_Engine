"""A name is not a run of Latin letters between two spaces.

Three name-matching primitives in `agents/common.py` were written as rules
about names and are rules about the Latin script:

  * `_significant_name_tokens` extracts tokens with `[A-Za-z']+`, so it
    returns the EMPTY SET for a name in any other script -- and `_recognizes`,
    which every identity floor in the file now asks, gives up on an empty set.
  * `_player_name_forms` splits on `[\\s,]` and keeps a part only if it opens
    with a CAPITAL, so a name joined by a middle dot never splits and a
    caseless script never contributes a part at all.
  * `_subject_opener` ends its pattern with `\\b`, which asserts a transition
    between word and non-word characters -- a description of scripts that put
    spaces between words. A Japanese particle is a word character, so
    「ヒナミは」 does not match `ヒナミ\\b` and the sentence-subject resolution
    every player-act and character-act guard is built on returns nobody. Not
    merely for name PARTS: the full registered name fails too.

All three fail closed -- the guard goes quiet rather than loud -- which is why
a green suite and a running story both looked fine. `character_schema` already
owns the answer (`name_boundary_pattern`, `_UNSPACED_SCRIPT`), written for
exactly this and applied at the identity scrub; these three sites were missed.

The Latin cases here are the control: every one of them behaved this way
before and must keep behaving this way.
"""

from __future__ import annotations

import pytest

from agents.common import (_player_name_forms, _recognizes, _sentence_subjects,
                           _significant_name_tokens, _subject_opener)


JA_FULL = "佐藤・ヒナミ"
JA_SENTENCE = "ヒナミは棚に手を伸ばす。"


# ---- tokens ---------------------------------------------------------------

def test_a_japanese_name_has_identifying_tokens():
    assert _significant_name_tokens(JA_FULL) == {"佐藤", "ヒナミ"}


def test_the_variant_rule_works_in_a_caseless_script():
    """The rule `_recognizes` exists for: a mind introduced to the whole name
    knows the person by one part of it."""
    assert _recognizes("ヒナミ", {JA_FULL})


def test_a_stranger_sharing_a_family_name_is_still_a_stranger():
    """The tightness that makes the rule safe, in this script too."""
    assert not _recognizes("佐藤・タロウ", {JA_FULL})


def test_latin_tokens_are_unchanged():
    assert _significant_name_tokens("William T. Riker") == {"william", "riker"}
    assert _significant_name_tokens("Commander Riker") == {"riker"}


# ---- standalone forms -----------------------------------------------------

def test_a_dot_joined_name_yields_its_parts():
    forms = _player_name_forms(JA_FULL)
    assert JA_FULL in forms and "ヒナミ" in forms and "佐藤" in forms


def test_latin_forms_are_unchanged():
    assert _player_name_forms("Hinami Sato") == ["Hinami Sato", "Hinami", "Sato"]
    assert "The" not in _player_name_forms("The Stranger")
    assert "Jo" not in _player_name_forms("Jo Anne")


# ---- sentence subjects ----------------------------------------------------

def test_a_particle_is_not_the_end_of_a_name():
    assert _subject_opener(JA_FULL).match("佐藤・ヒナミは棚に手を伸ばす。")
    assert _subject_opener("ヒナミ").match(JA_SENTENCE)


def test_the_subject_of_a_japanese_sentence_resolves():
    assert list(_sentence_subjects(JA_SENTENCE, [JA_FULL])) == [
        (JA_SENTENCE, JA_FULL)]


def test_a_latin_name_still_refuses_to_match_inside_a_longer_word():
    """The boundary that IS applied: `Hinamis` is not `Hinami`."""
    assert not _subject_opener("Hinami").match("Hinamis reaches for it.")
    assert _subject_opener("Hinami").match("Hinami reaches for it.")


def test_latin_sentence_subjects_are_unchanged():
    assert list(_sentence_subjects("Hinami reaches for the shelf.",
                                   ["Hinami Sato"])) == [
        ("Hinami reaches for the shelf.", "Hinami Sato")]
    assert list(_sentence_subjects("The Dalek's own base grinds forward.",
                                   ["A Dalek"])) == [
        ("The Dalek's own base grinds forward.", "A Dalek")]
